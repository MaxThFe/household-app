import asyncio
import json
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Roborock status state codes that mean the mop is still being washed at the dock.
# See roborock/data/v1/v1_code_mappings.py (washing_the_mop=23, washing_the_mop_2=25,
# going_to_wash_the_mop=26).
_WASHING_STATES = {23, 25, 26}

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
    from roborock import RoborockCommand
    from roborock.devices.device_manager import UserParams, create_device_manager
    from roborock.web_api import UserData

    token = _load_token()
    if not token:
        logger.error("Roborock not authenticated — run setup first")
        return

    device_manager = None
    try:
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
                await device.v1_properties.command.send(RoborockCommand.APP_START)
                logger.info("Cleaning started on %s", device.name)
                break
        else:
            logger.warning("No compatible Roborock device found")
    except Exception:
        logger.exception("Failed to start Roborock cleaning")
    finally:
        if device_manager is not None:
            try:
                await device_manager.close()
            except Exception:
                logger.exception("Failed to close Roborock device manager")


async def wash_mop_then_goto() -> None:
    """Wash the mop at the dock, wait for it to finish, then send the robot to a
    fixed target location on the map where it parks (no cleaning)."""
    from roborock import RoborockCommand
    from roborock.devices.device_manager import UserParams, create_device_manager
    from roborock.web_api import UserData

    token = _load_token()
    if not token:
        logger.error("Roborock not authenticated — run setup first")
        return

    device_manager = None
    try:
        user_data = UserData.from_dict(token["user_data"])
        user_params = UserParams(
            username=token["username"],
            user_data=user_data,
            base_url=token["base_url"],
        )
        device_manager = await create_device_manager(user_params)
        devices = await device_manager.get_devices()

        for device in devices:
            if not device.v1_properties:
                continue

            command = device.v1_properties.command

            await command.send(RoborockCommand.APP_START_WASH)
            logger.info("Mop washing started on %s", device.name)

            # Give the robot a moment to actually enter the washing state.
            await asyncio.sleep(20)

            # Poll until washing finishes, with a safety timeout (~5 min).
            for _ in range(60):
                status = await command.send(RoborockCommand.GET_STATUS)
                state = _extract_state(status)
                if state not in _WASHING_STATES:
                    logger.info("Mop washing finished (state=%s)", state)
                    break
                await asyncio.sleep(10)
            else:
                logger.warning("Mop washing did not finish within timeout, sending goto anyway")

            await command.send(
                RoborockCommand.APP_GOTO_TARGET,
                [settings.vacuum_goto_target_x, settings.vacuum_goto_target_y],
            )
            logger.info(
                "Robot sent to target (%s, %s) on %s",
                settings.vacuum_goto_target_x,
                settings.vacuum_goto_target_y,
                device.name,
            )
            break
        else:
            logger.warning("No compatible Roborock device found")
    except Exception:
        logger.exception("Failed to wash mop and send robot to target")
    finally:
        if device_manager is not None:
            try:
                await device_manager.close()
            except Exception:
                logger.exception("Failed to close Roborock device manager")


def _extract_state(status) -> int | None:
    """Pull the integer state code out of a GET_STATUS response, which may be a
    dataclass with a ``state`` attribute or a raw dict."""
    state = getattr(status, "state", None)
    if state is None and isinstance(status, dict):
        state = status.get("state")
    return int(state) if state is not None else None


def is_authenticated() -> bool:
    return _load_token() is not None
