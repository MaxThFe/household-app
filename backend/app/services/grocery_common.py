"""What every grocery source turns its receipts into, plus shared plumbing.

Each store client (grocery_picnic, grocery_ah, grocery_lidl) yields Receipts;
grocery_sync stores them. Money is integer cents throughout: the stores send
floats (AH) or locale strings like "1.234,56" (Lidl), and summing floats is
how cent drift creeps into totals.
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings

LOCAL_TZ = ZoneInfo("Europe/Amsterdam")


class NotConnected(Exception):
    """No usable login for this account — run grocery_setup.py."""


@dataclass
class Item:
    name: str
    product_id: str | None = None
    quantity: float | None = None
    unit: str = ""  # 'kg' for weighed articles, else quantity counts packs
    unit_quantity: str = ""  # pack size as the store prints it, e.g. "500 gram"
    unit_price_cents: int | None = None
    amount_cents: int | None = None  # the line before discounts
    discount_cents: int = 0  # what came off the line, as a positive number


@dataclass
class Receipt:
    store: str
    external_id: str
    person: str
    purchased_at: datetime  # timezone-aware
    total_cents: int
    raw: dict
    store_name: str = ""
    items: list[Item] = field(default_factory=list)


def since() -> datetime:
    """The first moment worth fetching (settings.grocery_since, local time)."""
    return datetime.fromisoformat(settings.grocery_since).replace(tzinfo=LOCAL_TZ)


def parse_datetime(value: str) -> datetime:
    """ISO timestamp from a store; one without an offset is taken as local."""
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=LOCAL_TZ)


def local_iso(moment: datetime) -> str:
    return moment.astimezone(LOCAL_TZ).strftime("%Y-%m-%dT%H:%M:%S")


def _to_decimal(value, *, grouped: bool = True) -> Decimal | None:
    """A number from a store: 2.19, "2,19", "1.234,56", "-0,21", "1,10-".

    grouped says whether a lone dot can be a thousands separator. True for
    money ("1.234" is a thousand euro), false for quantities, where "0.792"
    is a weight in kilos and "1.000" is one item.
    """
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip()
    negative = text.startswith("-") or text.endswith("-")
    text = re.sub(r"[^\d.,]", "", text)
    if not text:
        return None
    if "." in text and "," in text:
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
        text = text.replace("." if decimal_sep == "," else ",", "").replace(decimal_sep, ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif "." in text and grouped:
        tail = text.rsplit(".", 1)[1]
        if len(tail) > 2 or text.count(".") > 1:
            text = text.replace(".", "")
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return -number if negative else number


def euros_to_cents(value) -> int | None:
    number = _to_decimal(value)
    if number is None:
        return None
    return int((number * 100).to_integral_value(rounding=ROUND_HALF_UP))


def parse_quantity(value) -> float | None:
    number = _to_decimal(value, grouped=False)
    return None if number is None else float(number)


# --- login tokens --------------------------------------------------------------
# One JSON file per store and person next to the database, like the Picnic and
# Roborock tokens. AH and Lidl both rotate the refresh token on every renewal,
# so the file is rewritten each time and must never be left half-written.

def _slug(person: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", person.lower()).strip("_")


def token_path(store: str, person: str) -> Path:
    return Path(settings.database_path).parent / f"{store}_token_{_slug(person)}.json"


def load_token(store: str, person: str) -> dict | None:
    path = token_path(store, person)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_token(store: str, person: str, token: dict) -> None:
    path = token_path(store, person)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(token, handle)
    tmp.replace(path)


def connected_people(store: str) -> list[str]:
    return [
        p for p in (settings.user1_name, settings.user2_name)
        if token_path(store, p).exists()
    ]


def extract_code(pasted: str) -> str:
    """The authorisation code from a pasted redirect URL, or a bare code."""
    pasted = pasted.strip().strip("'\"")
    match = re.search(r"[?&#]code=([^&\s#]+)", pasted)
    if match:
        from urllib.parse import unquote

        return unquote(match.group(1))
    if re.fullmatch(r"[A-Za-z0-9._~\-]+", pasted):
        return pasted
    raise ValueError("That is neither the redirect URL nor a code")
