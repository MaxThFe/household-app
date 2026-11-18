"""Picnic orders, through the login picnic_client already keeps per user.

The household shares one Picnic account, so orders carry no person. Every
connected login is read and orders are matched on their id, so it does not
matter which of the logins the shared account is.

A delivery holds one or more orders (a top-up order rides along with the
main one). Each order line has one article; its QUANTITY decorator is the
count, line price the undiscounted total, and a PRICE decorator, when there
is one, the line total after the promotion. The PRICE decorator sits on the
article for some promotions and on the line itself for others.
"""

import asyncio

from app.services import picnic_client
from app.services.grocery_common import Item, Receipt, parse_datetime, since

STORE = "picnic"


def accounts() -> list[str]:
    return picnic_client.connected_users()


def _decorator(kind: str, *holders: dict) -> dict | None:
    for holder in holders:
        for decorator in holder.get("decorators") or []:
            if decorator.get("type") == kind:
                return decorator
    return None


def _items(order: dict) -> list[Item]:
    items = []
    for line in order.get("items") or []:
        articles = line.get("items") or []
        if not articles:
            continue
        article = articles[0]
        amount = line.get("price")
        promo = _decorator("PRICE", line, article)
        discounted = promo.get("display_price") if promo else None
        quantity = _decorator("QUANTITY", article, line)
        items.append(Item(
            name=article.get("name") or "",
            product_id=article.get("id"),
            quantity=float(quantity["quantity"]) if quantity and quantity.get("quantity") else None,
            unit_quantity=article.get("unit_quantity") or "",
            amount_cents=amount,
            discount_cents=max(amount - discounted, 0) if amount is not None and discounted is not None else 0,
        ))
    return items


def receipts_from_delivery(delivery: dict) -> list[Receipt]:
    when = (
        (delivery.get("delivery_time") or {}).get("start")
        or (delivery.get("eta2") or {}).get("start")
        or delivery["slot"]["window_start"]
    )
    receipts = []
    for order in delivery.get("orders") or []:
        if order.get("status") != "COMPLETED":
            continue
        total = order.get("checkout_total_price")
        receipts.append(Receipt(
            store=STORE,
            external_id=order["id"],
            person=None,
            purchased_at=parse_datetime(when),
            # checkout_total_price includes the bag and bottle deposits.
            total_cents=total if total is not None else order["total_price"],
            raw={**delivery, "orders": [order]},
            items=_items(order),
        ))
    return receipts


def _new_since(account: str, known: set[str]) -> list[dict]:
    def fetch(api):
        start = since()
        wanted = []
        for summary in api.get_deliveries():
            raw = summary.raw
            if raw.get("status") != "COMPLETED":
                continue
            if parse_datetime(raw["slot"]["window_start"]) < start:
                continue
            ids = {o["id"] for o in raw.get("orders") or []}
            if ids and ids <= known:
                continue
            wanted.append(raw["delivery_id"])
        return [api.get_delivery(delivery_id).raw for delivery_id in wanted]

    return picnic_client._call(account, fetch)


async def fetch(account: str, known: set[str]) -> list[Receipt]:
    deliveries = await asyncio.to_thread(_new_since, account, known)
    return [r for d in deliveries for r in receipts_from_delivery(d) if r.external_id not in known]
