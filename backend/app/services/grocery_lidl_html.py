"""Line items from the printed-receipt HTML of a Dutch Lidl Plus receipt.

Dutch receipts (ticketType "HTML") have no item array: everything is in
htmlPrintedReceipt, a monospace copy of the paper receipt. Each article span
carries its data as attributes, and one printed line can be split over
several spans that share an id:

    <span id="purchase_list_line_2" class="article" data-art-id="0080000"
          data-art-quantity="0,792" data-unit-price="1,39"
          data-art-description="Bananen">Bananen        1,10 B</span>

Lines without an article id that carry an amount are either discounts on the
article above (class "discount", a promotion id, or no class at all, as with
"In prijs verlaagd") or standalone lines such as returned deposit.

Adapted from github.com/erwindamsma/lidl-receipts-analyser (receipt_html.py).
"""

import re
from html.parser import HTMLParser

_LINE_ID = re.compile(r"^purchase_list_line_(\d+)$")
# A trailing amount, optionally followed by the VAT group letter.
_TRAILING_AMOUNT = re.compile(r"(-?\d[\d.,]*[.,]\d{2}-?)\s*([A-Z])?\s*$")
_WEIGHT_HINT = re.compile(r"\bkg\b")


class _Line:
    def __init__(self) -> None:
        self.text = ""
        self.classes: set[str] = set()
        self.attrs: dict[str, str] = {}


class _PurchaseListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lines: dict[int, _Line] = {}
        self._open: list[int | None] = []

    def handle_starttag(self, tag, attrs):
        if tag != "span":
            return
        attr_map = {k: v or "" for k, v in attrs}
        match = _LINE_ID.match(attr_map.get("id", ""))
        if not match:
            self._open.append(None)
            return
        number = int(match.group(1))
        line = self.lines.setdefault(number, _Line())
        line.classes.update(attr_map.get("class", "").split())
        line.attrs.update({k: v for k, v in attr_map.items() if k.startswith("data-")})
        self._open.append(number)

    def handle_endtag(self, tag):
        if tag == "span" and self._open:
            self._open.pop()

    def handle_data(self, data):
        if self._open and self._open[-1] is not None:
            self.lines[self._open[-1]].text += data


def _split_amount(text: str) -> tuple[str | None, str]:
    match = _TRAILING_AMOUNT.search(text)
    if not match:
        return None, text.strip()
    return match.group(1), text[: match.start()].strip()


def _clean_name(description: str, art_id: str) -> str:
    """Non-food articles print as "Bandschuurmachine-0502092"; drop the id."""
    suffix = f"-{art_id}"
    if art_id and description.endswith(suffix):
        return description[: -len(suffix)].strip()
    return description.strip()


def parse_receipt_html(html: str) -> list[dict]:
    """Items shaped like the itemsLine array other countries get."""
    parser = _PurchaseListParser()
    parser.feed(html)
    parser.close()

    items: list[dict] = []
    current: dict | None = None
    for number in sorted(parser.lines):
        line = parser.lines[number]
        text = line.text.rstrip()
        if not text.strip() or "currency" in line.classes:
            continue

        art_id = line.attrs.get("data-art-id", "")
        if art_id:
            amount, _ = _split_amount(text)
            if amount is None:
                # The "0,792 kg x 1,39 EUR/kg" line under a weighed article.
                if current is not None and _WEIGHT_HINT.search(text):
                    current["isWeight"] = True
                continue
            current = {
                "name": _clean_name(line.attrs.get("data-art-description", ""), art_id),
                "quantity": line.attrs.get("data-art-quantity") or "1",
                "currentUnitPrice": line.attrs.get("data-unit-price"),
                "originalAmount": amount,
                "codeInput": art_id,
                "isWeight": False,
                "discounts": [],
            }
            items.append(current)
            continue

        amount, description = _split_amount(text)
        if amount is None:
            continue
        is_discount = (
            "discount" in line.classes
            or "data-promotion-id" in line.attrs
            or not line.classes
        )
        if is_discount and current is not None:
            current["discounts"].append({"description": description, "amount": amount})
            continue
        # Standalone, e.g. returned deposit ("Emballage"): its own line, so the
        # money is not pinned on the article above.
        items.append({
            "name": description,
            "quantity": "1",
            "currentUnitPrice": amount,
            "originalAmount": amount,
            "codeInput": "",
            "isWeight": False,
            "discounts": [],
        })
        current = None
    return items
