"""One-time Roborock authentication setup.

Run this on the Pi to authenticate with Roborock's cloud API.
A login code will be sent to the email configured in HT_ROBOROCK_USERNAME.
The resulting token is saved to data/roborock_token.json for the scheduler.

Usage:
    python roborock_setup.py
"""

import asyncio

from app.core.config import settings
from app.services.roborock import request_login_code, verify_login_code, is_authenticated


async def main() -> None:
    if not settings.roborock_username:
        print("Error: HT_ROBOROCK_USERNAME is not set in your .env file.")
        return

    if is_authenticated():
        print("Already authenticated. Delete data/roborock_token.json to re-authenticate.")
        return

    print(f"Requesting login code for {settings.roborock_username}...")
    await request_login_code()
    print(f"A login code has been sent to {settings.roborock_username}.")

    code = input("Enter the code: ").strip()
    if not code:
        print("No code entered, aborting.")
        return

    await verify_login_code(code)
    print("Authentication successful! Token saved to data/roborock_token.json")


if __name__ == "__main__":
    asyncio.run(main())
