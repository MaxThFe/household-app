"""Albert Heijn in-store receipts (kassabonnen), through the Appie app's API.

Unofficial: the endpoints, headers and queries are the iOS app's, as worked
out by github.com/gwillem/appie-go. Login happens once in a browser (see
grocery_setup.py); after that the refresh token keeps it going. AH hands out
a new refresh token with every renewal, so it is saved each time.
"""

import time

import httpx

from app.services.grocery_common import (
    Item,
    NotConnected,
    Receipt,
    connected_people,
    euros_to_cents,
    load_token,
    parse_datetime,
    save_token,
    since,
)

STORE = "ah"
API = "https://api.ah.nl"
CLIENT_ID = "appie-ios"
CLIENT_VERSION = "9.28"
LOGIN_URL = (
    "https://login.ah.nl/login?client_id=appie-ios&response_type=code"
    "&redirect_uri=appie://login-exit"
)
HEADERS = {
    "User-Agent": f"Appie/{CLIENT_VERSION} (iPhone17,3; iPhone; CPU OS 26_1 like Mac OS X)",
    "x-client-name": CLIENT_ID,
    "x-client-version": CLIENT_VERSION,
    "x-application": "AHWEBSHOP",
    "Accept": "application/json",
}
PAGE_SIZE = 50

RECEIPTS_QUERY = """query FetchPosReceipts($offset: Int!, $limit: Int!) {
  posReceiptsPage(pagination: {offset: $offset, limit: $limit}) {
    posReceipts { id dateTime totalAmount { amount } }
  }
}"""

RECEIPT_QUERY = """query FetchReceipt($id: String!) {
  posReceiptDetails(id: $id) {
    id
    products { id quantity name price { amount } amount { amount } }
    discounts { name amount { amount } }
    payments { method amount { amount } }
  }
}"""


def accounts() -> list[str]:
    return connected_people(STORE)


def _store_token(person: str, data: dict) -> dict:
    token = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        # Renew a minute early so a request never races the expiry.
        "expires_at": time.time() + int(data.get("expires_in") or 3600) - 60,
    }
    save_token(STORE, person, token)
    return token


async def exchange_code(person: str, code: str) -> None:
    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as http:
        response = await http.post(
            f"{API}/mobile-auth/v1/auth/token", json={"clientId": CLIENT_ID, "code": code}
        )
        response.raise_for_status()
        _store_token(person, response.json())


async def _access_token(http: httpx.AsyncClient, person: str) -> str:
    token = load_token(STORE, person)
    if not token:
        raise NotConnected(f"{person} has no AH login — run grocery_setup.py ah {person}")
    if time.time() < token.get("expires_at", 0):
        return token["access_token"]
    response = await http.post(
        f"{API}/mobile-auth/v1/auth/token/refresh",
        json={"clientId": CLIENT_ID, "refreshToken": token["refresh_token"]},
    )
    if response.status_code in (400, 401, 403):
        raise NotConnected(f"{person}'s AH login expired — run grocery_setup.py ah {person}")
    response.raise_for_status()
    return _store_token(person, response.json())["access_token"]


async def _graphql(http: httpx.AsyncClient, person: str, query: str, variables: dict) -> dict:
    token = await _access_token(http, person)
    response = await http.post(
        f"{API}/graphql",
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(f"AH GraphQL: {body['errors'][0].get('message')}")
    return body["data"]


def parse_receipt(person: str, summary: dict, detail: dict) -> Receipt:
    items = []
    for product in detail.get("products") or []:
        price = product.get("price") or {}
        items.append(Item(
            name=product.get("name") or "",
            product_id=str(product["id"]) if product.get("id") is not None else None,
            quantity=product.get("quantity"),
            unit_price_cents=euros_to_cents(price.get("amount")),
            amount_cents=euros_to_cents((product.get("amount") or {}).get("amount")),
        ))
    # Bonus and other discounts come as receipt-level lines, not per product.
    return Receipt(
        store=STORE,
        external_id=summary["id"],
        person=person,
        purchased_at=parse_datetime(summary["dateTime"]),
        total_cents=euros_to_cents(summary["totalAmount"]["amount"]),
        raw={"summary": summary, "detail": detail},
        items=items,
    )


async def fetch(person: str, known: set[str]) -> list[Receipt]:
    start = since()
    receipts = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as http:
        offset = 0
        while True:
            data = await _graphql(http, person, RECEIPTS_QUERY, {"offset": offset, "limit": PAGE_SIZE})
            page = data["posReceiptsPage"]["posReceipts"] or []
            for summary in page:
                if summary["id"] in known or parse_datetime(summary["dateTime"]) < start:
                    continue
                detail = await _graphql(http, person, RECEIPT_QUERY, {"id": summary["id"]})
                receipts.append(parse_receipt(person, summary, detail["posReceiptDetails"]))
            # Newest first: once a whole page is older than wanted, stop.
            if len(page) < PAGE_SIZE or all(parse_datetime(r["dateTime"]) < start for r in page):
                break
            offset += PAGE_SIZE
    return receipts
