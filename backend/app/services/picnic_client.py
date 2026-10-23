"""Picnic (unofficial API) — product search and filling the cart.

Each user has their own Picnic account, so an order lands in the cart of
whoever places it. The catalogue is the same for everyone, so searching uses
any account that is logged in.

The library is synchronous, so every call runs in a thread. Each user's auth
token is kept next to the database like the Roborock one; picnic_setup.py
creates it, since a fresh login asks for an SMS code. When a token expires we
try the password login again, which works as long as Picnic doesn't ask for
2FA.
"""

import asyncio
import json
import logging
import re
import threading
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

IMAGE_URL = "https://storefront-prod.{country}.picnicinternational.com/static/images/{image_id}/small.png"

_apis: dict[str, object] = {}
_lock = threading.Lock()


class PicnicNotConnected(Exception):
    """No usable login for this user — run picnic_setup.py."""


def credentials(user: str) -> tuple[str, str]:
    """(email, password) for an app user, empty when they have no account."""
    if user == settings.user1_name:
        return settings.picnic_user1_email, settings.picnic_user1_password
    if user == settings.user2_name:
        return settings.picnic_user2_email, settings.picnic_user2_password
    return "", ""


def token_path(user: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", user.lower()).strip("_")
    return Path(settings.database_path).parent / f"picnic_token_{slug}.json"


def _save_token(user: str, token: str) -> None:
    token_path(user).write_text(json.dumps({"auth_token": token}))


def _load_token(user: str) -> str | None:
    path = token_path(user)
    if path.exists():
        return json.loads(path.read_text()).get("auth_token")
    return None


def is_authenticated(user: str) -> bool:
    return _load_token(user) is not None


def connected_users() -> list[str]:
    return [u for u in (settings.user1_name, settings.user2_name) if is_authenticated(u)]


def image_url(image_id: str | None) -> str | None:
    if not image_id:
        return None
    return IMAGE_URL.format(country=settings.picnic_country_code.lower(), image_id=image_id)


def _client(user: str):
    from python_picnic_api2 import PicnicAPI

    if user not in _apis:
        token = _load_token(user)
        if not token:
            raise PicnicNotConnected(f"{user} has no Picnic login — run picnic_setup.py")
        _apis[user] = PicnicAPI(auth_token=token, country_code=settings.picnic_country_code)
    return _apis[user]


def _relogin(user: str) -> None:
    from python_picnic_api2 import PicnicAPI
    from python_picnic_api2.session import Picnic2FARequired

    email, password = credentials(user)
    if not (email and password):
        raise PicnicNotConnected(f"{user}'s Picnic login expired — run picnic_setup.py")
    api = PicnicAPI(country_code=settings.picnic_country_code)
    try:
        api.login(email, password)
    except Picnic2FARequired as exc:
        raise PicnicNotConnected(f"Picnic wants an SMS code for {user} — run picnic_setup.py") from exc
    _save_token(user, api.session.auth_token)
    _apis[user] = api


def _call(user: str, fn):
    """Run fn(api) as this user, logging in again once if the token has expired."""
    from python_picnic_api2.session import PicnicAuthError

    with _lock:
        api = _client(user)
        try:
            result = fn(api)
        except PicnicAuthError:
            logger.info("Picnic token for %s rejected, logging in again", user)
            _relogin(user)
            api = _apis[user]
            result = fn(api)
        # Picnic rotates the token in response headers; keep the latest.
        if api.session.auth_token != _load_token(user):
            _save_token(user, api.session.auth_token)
        return result


def _product(item) -> dict:
    return {
        "product_id": item.id,
        "name": item.name or "",
        "unit_quantity": item.unit_quantity or "",
        "price": item.display_price,
        "image_id": item.image_id,
    }


async def search(query: str, limit: int = 12) -> list[dict]:
    users = connected_users()
    if not users:
        raise PicnicNotConnected("Nobody is logged in to Picnic — run picnic_setup.py")
    result = await asyncio.to_thread(_call, users[0], lambda api: api.search(query))
    return [_product(item) for item in result.items[:limit] if item.id]


async def add_product(user: str, product_id: str, count: int) -> None:
    await asyncio.to_thread(_call, user, lambda api: api.add_product(product_id, count))
