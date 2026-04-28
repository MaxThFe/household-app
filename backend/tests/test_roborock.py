"""Quick test to verify Roborock connectivity and list devices."""

import asyncio
import json
from pathlib import Path

from app.core.config import settings


async def main() -> None:
    from roborock.devices.device_manager import UserParams, create_device_manager
    from roborock.web_api import UserData

    token_path = Path(settings.database_path).parent / "roborock_token.json"
    token = json.loads(token_path.read_text())

    user_data = UserData.from_dict(token["user_data"])
    user_params = UserParams(
        username=token["username"],
        user_data=user_data,
        base_url=token["base_url"],
    )

    print("Connecting to Roborock cloud...")
    device_manager = await create_device_manager(user_params)
    devices = await device_manager.get_devices()

    if not devices:
        print("No devices found.")
        return

    for device in devices:
        print(f"\nDevice: {device.name}")
        print(f"  Model: {device.model}")
        if device.v1_properties:
            print(f"  Status: {device.v1_properties.status}")


if __name__ == "__main__":
    asyncio.run(main())
