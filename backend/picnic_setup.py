"""One-time Picnic authentication setup, per user.

Logs in with that user's HT_PICNIC_USER1_* / HT_PICNIC_USER2_* email and
password. Picnic usually asks for a code by SMS on a new device; enter it
here. The token is saved to data/picnic_token_<user>.json for the app.

Usage:
    python picnic_setup.py            # asks which user
    python picnic_setup.py <name>     # e.g. the name in HT_USER1_NAME
"""

import sys

from python_picnic_api2 import PicnicAPI
from python_picnic_api2.session import Picnic2FARequired

from app.core.config import settings
from app.services.picnic_client import _save_token, credentials, is_authenticated, token_path


def main() -> None:
    users = [settings.user1_name, settings.user2_name]
    user = sys.argv[1] if len(sys.argv) > 1 else input(f"Which user ({' / '.join(users)})? ").strip()
    if user not in users:
        print(f"Unknown user {user!r}; expected one of {users}.")
        return

    email, password = credentials(user)
    if not (email and password):
        slot = users.index(user) + 1
        print(f"Error: set HT_PICNIC_USER{slot}_EMAIL and HT_PICNIC_USER{slot}_PASSWORD in your .env file.")
        return

    if is_authenticated(user):
        print(f"{user} is already logged in. Delete {token_path(user)} to log in again.")
        return

    api = PicnicAPI(country_code=settings.picnic_country_code)
    try:
        api.login(email, password)
    except Picnic2FARequired:
        api.generate_2fa_code("SMS")
        code = input("Picnic sent a code by SMS. Enter it: ").strip()
        if not code:
            print("No code entered, aborting.")
            return
        api.verify_2fa_code(code)

    _save_token(user, api.session.auth_token)
    print(f"Logged in to Picnic as {api.get_user().firstname}. Token saved to {token_path(user)}")


if __name__ == "__main__":
    main()
