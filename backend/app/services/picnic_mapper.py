"""Picking the Picnic product for a shopping item, with an LLM.

One item at a time: the model searches Picnic as often as it needs (within a
cap) and ends on one of three calls — this product, ask the household, or not
something to buy at Picnic. The caller caches whatever comes back, so this
runs once per item, not once per order.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_SEARCHES = 6
MAX_TURNS = 10

INSTRUCTIONS = """\
You map items on a Dutch household's shopping list to products at Picnic, an
online supermarket in the Netherlands. Search Picnic (in Dutch works best,
English item names are fine to translate), then finish with exactly one of:

- choose_product: when one product is clearly what a household means by the
  item. Prefer the plain, everyday version (no organic/luxury/odd variants
  unless the item says so) and a common pack size.
- ask_user: only when the choice really is the household's to make — e.g.
  "cream" could be whipping or cooking cream, or minced meat comes as beef or
  half-half in 500 g and 1 kg packs. Ask one short question and offer 2-5
  products from your searches as candidates.
- not_on_picnic: for things Picnic doesn't sell or that aren't groceries.

The household writes quantities as a number of packs, so the pack you choose
is what one unit of the item means. Recipe names, when given, are a hint at
what the item is used for. Earlier answers from the household come first in
the conversation; follow them.
"""


def _function(name: str, description: str, properties: dict) -> dict:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


TOOLS = [
    _function(
        "search_picnic",
        "Search Picnic's catalogue. Returns up to 12 products with id, name, pack size and price in cents.",
        {"query": {"type": "string"}},
    ),
    _function(
        "choose_product",
        "Finish: this product (a product_id from a search) is the item.",
        {"product_id": {"type": "string"}},
    ),
    _function(
        "ask_user",
        "Finish: ask the household which product they mean.",
        {
            "question": {"type": "string"},
            "candidate_product_ids": {"type": "array", "items": {"type": "string"}},
        },
    ),
    _function(
        "not_on_picnic",
        "Finish: this item is not something to order at Picnic.",
        {"reason": {"type": "string"}},
    ),
]


@dataclass
class Chosen:
    product: dict


@dataclass
class Question:
    question: str
    candidates: list[dict] = field(default_factory=list)


@dataclass
class NotOnPicnic:
    reason: str


Outcome = Chosen | Question | NotOnPicnic
Search = Callable[[str], Awaitable[list[dict]]]


def _prompt(item: str, recipe_names: list[str], prior_qa: list[tuple[str, str]]) -> str:
    lines = []
    for question, answer in prior_qa:
        lines.append(f"Earlier you asked: {question}\nThe household answered: {answer}")
    lines.append(f"Shopping list item: {item}")
    if recipe_names:
        lines.append(f"Used in: {', '.join(recipe_names)}")
    return "\n\n".join(lines)


async def map_item(
    llm,
    model: str,
    search: Search,
    item: str,
    recipe_names: list[str] = (),
    prior_qa: list[tuple[str, str]] = (),
) -> Outcome:
    """Run the model until it finishes on one of the three outcomes.

    `llm` is an AsyncOpenAI client (or anything with responses.create).
    """
    seen: dict[str, dict] = {}
    searches = 0
    conversation: list = [{"role": "user", "content": _prompt(item, list(recipe_names), list(prior_qa))}]

    for _ in range(MAX_TURNS):
        response = await llm.responses.create(
            model=model, instructions=INSTRUCTIONS, input=conversation, tools=TOOLS,
        )
        conversation += response.output
        calls = [out for out in response.output if out.type == "function_call"]
        if not calls:
            # The model wrote prose instead of finishing; treat it as a question.
            text = response.output_text.strip()
            return Question(text or f"Which product do you mean by '{item}'?", list(seen.values())[:5])

        for call in calls:
            args = json.loads(call.arguments)
            if call.name == "choose_product":
                if args["product_id"] in seen:
                    return Chosen(seen[args["product_id"]])
                output = "Unknown product_id: choose one from your search results."
            elif call.name == "ask_user":
                candidates = [seen[pid] for pid in args["candidate_product_ids"] if pid in seen]
                return Question(args["question"], candidates)
            elif call.name == "not_on_picnic":
                return NotOnPicnic(args["reason"])
            elif call.name == "search_picnic":
                if searches >= MAX_SEARCHES:
                    output = "Search limit reached: finish with what you have."
                else:
                    searches += 1
                    results = await search(args["query"])
                    seen.update((p["product_id"], p) for p in results)
                    output = json.dumps(
                        [{k: p[k] for k in ("product_id", "name", "unit_quantity", "price")} for p in results],
                        ensure_ascii=False,
                    ) if results else "No results."
            else:
                output = f"Unknown tool {call.name}."
            conversation.append(
                {"type": "function_call_output", "call_id": call.call_id, "output": output}
            )

    logger.warning("Picnic mapping for %r did not finish within %d turns", item, MAX_TURNS)
    return Question(f"Which product do you mean by '{item}'?", list(seen.values())[:5])
