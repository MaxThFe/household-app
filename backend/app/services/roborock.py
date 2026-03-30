import json
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

TOKEN_PATH = Path(settings.database_path).parent / "roborock_token.json"


def _save_token(data: dict) -> None:
    TOKEN_PATH.write_text(json.dumps(data))


def _load_token() -> dict | None:
    if TOKEN_PATH.exists():
        return json.loads(TOKEN_PATH.read_text())
    return None


async def request_login_code() -> "RoborockApiClient":
    from roborock.web_api import RoborockApiClient

    client = RoborockApiClient(username=settings.roborock_username)
    await client.request_code()
    logger.info("Roborock login code sent to %s", settings.roborock_username)
    return client


async def verify_login_code(client: "RoborockApiClient", code: str) -> None:
    user_data = await client.code_login(code)
    base_url = await client.base_url
    _save_token({
        "username": settings.roborock_username,
        "user_data": user_data.as_dict(),
        "base_url": base_url,
    })
    logger.info("Roborock authentication successful, token saved")


async def start_cleaning() -> None:
    from roborock.devices.device_manager import UserParams, create_device_manager

    token = _load_token()
    if not token:
        logger.error("Roborock not authenticated — run setup first")
        return

    try:
        from roborock.web_api import UserData

        user_data = UserData.from_dict(token["user_data"])
        user_params = UserParams(
            username=token["username"],
            user_data=user_data,
            base_url=token["base_url"],
        )
        device_manager = await create_device_manager(user_params)
        devices = await device_manager.get_devices()

        for device in devices:
            if device.v1_properties:
                from roborock import RoborockCommand

                await device.v1_properties.command.send(RoborockCommand.APP_START)
                logger.info("Cleaning started on %s", device.name)
                break
        else:
            logger.warning("No compatible Roborock device found")
    except Exception:
        logger.exception("Failed to start Roborock cleaning")


def is_authenticated() -> bool:
    return _load_token() is not None
