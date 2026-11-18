"""Lidl receipts, through the Lidl Plus app's API.

Unofficial, the same API github.com/Andre0512/lidl-plus uses: an OAuth login
at accounts.lidl.com, the receipt list at tickets.lidlplus.com/api/v2 and one
receipt at /api/v3 (v2 no longer returns the Dutch receipts in full).

The login form is behind a captcha, so it happens once in a real browser
(grocery_setup.py) rather than in an automated one. Lidl replaces the refresh
token on every renewal and the old one stops working, so the new one is
saved straight away — losing it means logging in again.
"""

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.grocery_common import (
    Item,
    NotConnected,
    Receipt,
    connected_people,
    euros_to_cents,
    load_token,
    parse_datetime,
    parse_quantity,
    save_token,
    since,
)
from app.services.grocery_lidl_html import parse_receipt_html

STORE = "lidl"
AUTH_API = "https://accounts.lidl.com"
TICKETS_API = "https://tickets.lidlplus.com/api"
CLIENT_ID = "LidlPlusNativeClient"
REDIRECT_URI = "com.lidlplus.app://callback"
# The client secret is a public value baked into the app.
BASIC_AUTH = "Basic " + base64.b64encode(f"{CLIENT_ID}:secret".encode()).decode()


def accounts() -> list[str]:
    return connected_people(STORE)


# --- login --------------------------------------------------------------------

def login_url() -> tuple[str, str]:
    """(URL to log in at, PKCE verifier to finish the login with)."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    country = settings.lidl_country.upper()
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile offline_access lpprofile lpapis",
        "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "Country": country,
        "language": f"{settings.lidl_language.lower()}-{country}",
    }
    return f"{AUTH_API}/connect/authorize?{urlencode(params)}", verifier


async def _token_request(http: httpx.AsyncClient, form: dict) -> httpx.Response:
    # Never retried: a code is single-use and a refresh token rotates, so a
    # second attempt would spend a credential the first may have used up.
    return await http.post(f"{AUTH_API}/connect/token", data=form, headers={"Authorization": BASIC_AUTH})


def _store_token(person: str, data: dict) -> dict:
    token = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": time.time() + int(data.get("expires_in") or 3600) - 60,
    }
    save_token(STORE, person, token)
    return token


async def exchange_code(person: str, code: str, verifier: str) -> None:
    async with httpx.AsyncClient(timeout=20) as http:
        response = await _token_request(http, {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        })
        response.raise_for_status()
        _store_token(person, response.json())


async def _access_token(http: httpx.AsyncClient, person: str) -> str:
    token = load_token(STORE, person)
    if not token:
        raise NotConnected(f"{person} has no Lidl login — run grocery_setup.py lidl {person}")
    if time.time() < token.get("expires_at", 0):
        return token["access_token"]
    response = await _token_request(http, {
        "grant_type": "refresh_token", "refresh_token": token["refresh_token"],
    })
    if response.status_code in (400, 401):
        raise NotConnected(f"{person}'s Lidl login expired — run grocery_setup.py lidl {person}")
    response.raise_for_status()
    return _store_token(person, response.json())["access_token"]


async def _get(http: httpx.AsyncClient, person: str, path: str) -> dict:
    token = await _access_token(http, person)
    response = await http.get(f"{TICKETS_API}{path}", headers={
        "Authorization": f"Bearer {token}",
        "App-Version": settings.lidl_app_version,
        "Operating-System": "iOs",
        "App": "com.lidl.eci.lidl.plus",
        "Accept-Language": settings.lidl_language,
    })
    response.raise_for_status()
    return response.json()


# --- receipts -------------------------------------------------------------------

def _raw_items(ticket: dict) -> list[dict]:
    for key in ("itemsLine", "itemLines", "items"):
        if isinstance(ticket.get(key), list) and ticket[key]:
            return ticket[key]
    if ticket.get("htmlPrintedReceipt"):
        return parse_receipt_html(ticket["htmlPrintedReceipt"])
    return []


def _item(raw: dict) -> Item:
    is_weight = bool(raw.get("isWeight"))
    quantity = parse_quantity(raw.get("quantity"))
    unit_price = euros_to_cents(raw.get("currentUnitPrice"))
    amount = euros_to_cents(raw.get("originalAmount"))
    if amount is None and quantity is not None and unit_price is not None:
        amount = round(quantity * unit_price)
    discounts = sum(abs(euros_to_cents(d.get("amount")) or 0) for d in raw.get("discounts") or [])
    return Item(
        name=(raw.get("name") or "").strip(),
        product_id=raw.get("codeInput") or None,
        quantity=quantity,
        unit="kg" if is_weight else "",
        unit_price_cents=unit_price,
        amount_cents=amount,
        discount_cents=discounts,
    )


def parse_ticket(person: str, ticket: dict) -> Receipt:
    store = ticket.get("store") if isinstance(ticket.get("store"), dict) else {}
    return Receipt(
        store=STORE,
        external_id=ticket["id"],
        person=person,
        purchased_at=parse_datetime(ticket["date"]),
        total_cents=euros_to_cents(ticket.get("totalAmount")) or 0,
        store_name=store.get("name") or "",
        raw=ticket,
        items=[_item(r) for r in _raw_items(ticket)],
    )


async def fetch(person: str, known: set[str]) -> list[Receipt]:
    start = since()
    country = settings.lidl_country.upper()
    receipts = []
    async with httpx.AsyncClient(timeout=30) as http:
        page, seen = 1, 0
        while True:
            data = await _get(http, person, f"/v2/{country}/tickets?pageNumber={page}&onlyFavorite=false")
            tickets = data.get("tickets") or []
            for summary in tickets:
                if summary["id"] in known or parse_datetime(summary["date"]) < start:
                    continue
                ticket = await _get(http, person, f"/v3/{country}/tickets/{summary['id']}")
                receipts.append(parse_ticket(person, ticket))
            seen += len(tickets)
            # Newest first: stop at the end, or once a page is all too old.
            if (
                not tickets
                or seen >= int(data.get("totalCount") or 0)
                or all(parse_datetime(t["date"]) < start for t in tickets)
            ):
                break
            page += 1
    return receipts
