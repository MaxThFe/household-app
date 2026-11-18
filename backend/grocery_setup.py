"""One-time AH or Lidl login for the grocery spending sync, per person.

Two steps, so the code can be pasted in whenever the browser part is done:

    docker compose exec backend python grocery_setup.py ah Max          # prints the login URL
    docker compose exec backend python grocery_setup.py ah Max '<link>' # finishes the login

(the same with lidl). Both stores log in through their app's own login page,
which ends by sending the browser to an app link (appie://login-exit?code=...
or com.lidlplus.app://callback?code=...) that a desktop browser cannot open.
That link carries the code:

  1. Open the printed URL in a browser, with the developer tools (F12)
     open on the Network tab and "Preserve log" ticked, and log in.
  2. When the page stops, find the last request to login.ah.nl or
     accounts.lidl.com: its "Location" response header is the app link.
     Chrome's Console also shows it, as "Failed to launch 'appie://...'".
  3. Run the second step with that whole link (or just the code), quickly:
     the code expires within minutes.

The token lands in data/<store>_token_<person>.json; the script then syncs
that account once to prove it works.
"""

import asyncio
import json
import sys

import aiosqlite

from app.core.config import settings
from app.core.database import init_db
from app.services import grocery_ah, grocery_lidl, grocery_sync
from app.services.grocery_common import extract_code, token_path


def _verifier_path(person: str):
    # Lidl's login is tied to a PKCE verifier made in step one.
    return token_path("lidl", person).with_name(token_path("lidl", person).stem + "_pkce.json")


def start(store: str, person: str) -> None:
    if store == "ah":
        url = grocery_ah.LOGIN_URL
    else:
        url, verifier = grocery_lidl.login_url()
        _verifier_path(person).write_text(json.dumps({"verifier": verifier}))
    print(f"Log in as {person} here:\n\n  {url}\n")
    print(f"Then run: python grocery_setup.py {store} {person} '<the app link or code>'")


async def finish(store: str, person: str, pasted: str) -> None:
    code = extract_code(pasted)
    if store == "ah":
        await grocery_ah.exchange_code(person, code)
    else:
        path = _verifier_path(person)
        if not path.exists():
            print(f"Run step one first: python grocery_setup.py lidl {person}")
            return
        await grocery_lidl.exchange_code(person, code, json.loads(path.read_text())["verifier"])
        path.unlink()
    print(f"Logged in. Token saved to {token_path(store, person)}")

    await init_db()
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        try:
            added = await grocery_sync.sync_account(db, store, person)
        except Exception as exc:
            print(f"The first sync failed: {type(exc).__name__}: {exc}")
            return
    print(f"First sync done: {added} receipts since {settings.grocery_since}.")


def main() -> None:
    people = [settings.user1_name, settings.user2_name]
    args = sys.argv[1:]
    if len(args) not in (2, 3) or args[0] not in ("ah", "lidl") or args[1] not in people:
        print(f"Usage: python grocery_setup.py ah|lidl {'|'.join(people)} [app link or code]")
        return
    if len(args) == 2:
        start(args[0], args[1])
    else:
        asyncio.run(finish(*args))


if __name__ == "__main__":
    main()
