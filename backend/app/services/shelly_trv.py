"""Shelly BLU TRV radiator valves, reached through a Shelly BLU Gateway Gen3.

The valves only speak Bluetooth, to the gateway; the gateway exposes them over
its local RPC API, so no cloud account is involved. Reads come from the status
the gateway keeps cached for each valve. A write has to open a Bluetooth
connection to the valve: under a second with a good signal, never with a weak
one (the gateway reports connect_failed and the call times out).

The gateway is easily overwhelmed — a handful of calls in flight and it stops
answering or restarts — so it is only ever asked one thing at a time: a slow
poll keeps the valve status in memory for the app to read, and setpoint changes
queue behind it.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# The valve's own range; it refuses anything outside it.
MIN_TARGET_C = 4.0
MAX_TARGET_C = 30.0

# A healthy call lands in well under a second; one that has not after 10 s
# will not, and the gateway would only give up on it after a minute.
_TIMEOUT = 10.0
POLL_INTERVAL_SECONDS = 60
# Breathing room between consecutive calls within one poll.
_CALL_GAP_SECONDS = 1.0

# Every call to the gateway holds this, so there is never more than one.
_gateway_lock = asyncio.Lock()


class TrvError(Exception):
    """The gateway could not be reached, or it could not reach the valve."""

    def __init__(self, message: str, timeout: bool = False):
        super().__init__(message)
        self.timeout = timeout


def trv_rooms() -> dict[str, str]:
    """Configured MAC (upper case) -> room name, in display order."""
    pairs = (
        (settings.trv_living_room_mac, "Living room"),
        (settings.trv_bedroom_mac, "Bedroom"),
        (settings.trv_kitchen_mac, "Kitchen"),
    )
    return {mac.strip().upper(): room for mac, room in pairs if mac.strip()}


# Bluetooth MAC -> the gateway's blutrv component id; only changes on re-pairing.
_valve_ids: dict[str, int] = {}
# Room -> latest state, as served to the app.
_states: dict[str, dict] = {}
# The gateway's cached status lags a write until the valve next reports, so a
# target set from here wins over any status older than it: room -> (target, ts).
_written: dict[str, tuple[float, float]] = {}


async def _rpc(client: httpx.AsyncClient, method: str, params: dict) -> dict:
    url = f"http://{settings.shelly_gateway_host}/rpc"
    async with _gateway_lock:
        try:
            res = await client.post(url, json={"id": 1, "method": method, "params": params})
        except httpx.TimeoutException as e:
            raise TrvError(f"{method}: no answer in {_TIMEOUT:.0f} s", timeout=True) from e
        except httpx.HTTPError as e:
            raise TrvError(f"{method}: gateway unreachable ({e})") from e
    body = res.json()
    if "error" in body:
        error = body["error"]
        raise TrvError(f"{method}: {error.get('message')}", timeout=error.get("code") == 504)
    return body["result"]


async def _load_valve_ids(client: httpx.AsyncClient) -> None:
    ids: dict[str, int] = {}
    offset = 0
    while True:
        page = await _rpc(client, "Shelly.GetComponents", {"dynamic_only": True, "offset": offset})
        for comp in page["components"]:
            if comp["key"].startswith("blutrv:"):
                ids[comp["config"]["addr"].upper()] = comp["config"]["id"]
        offset += len(page["components"])
        if not page["components"] or offset >= page["total"]:
            break
        await asyncio.sleep(_CALL_GAP_SECONDS)
    _valve_ids.clear()
    _valve_ids.update(ids)


def _iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None


def _state(room: str, mac: str, link: dict, remote: dict) -> dict:
    """One room's thermostat from the gateway's link status and cached valve status."""
    trv = remote.get("status", {}).get("trv:0", {})
    target = trv.get("target_C")
    written = _written.get(room)
    if written and written[1] > remote.get("ts", 0):
        target = written[0]
    last_seen = link.get("last_updated_ts")
    return {
        "room": room,
        "mac": mac,
        "current_temperature": trv.get("current_C"),
        "target_temperature": target,
        "valve_position": trv.get("pos"),
        "battery": link.get("battery"),
        "last_seen": _iso(last_seen),
        "stale": last_seen is None
        or time.time() - last_seen > settings.sensor_stale_after_minutes * 60,
        # Advertisements still arrive, but writes cannot get through.
        "reachable": "connect_failed" not in link.get("errors", []),
    }


def get_thermostats() -> list[dict]:
    """Latest known state per configured room, in display order."""
    return [_states[room] for room in trv_rooms().values() if room in _states]


async def _poll(client: httpx.AsyncClient) -> None:
    rooms = trv_rooms()
    if not _valve_ids or any(mac not in _valve_ids for mac in rooms):
        await _load_valve_ids(client)
    for mac, room in rooms.items():
        valve_id = _valve_ids.get(mac)
        if valve_id is None:
            logger.warning("TRV %s (%s) is not paired with the gateway", mac, room)
            continue
        await asyncio.sleep(_CALL_GAP_SECONDS)
        link = await _rpc(client, "BluTrv.GetStatus", {"id": valve_id})
        await asyncio.sleep(_CALL_GAP_SECONDS)
        remote = await _rpc(client, "BluTrv.GetRemoteStatus", {"id": valve_id})
        _states[room] = _state(room, mac, link, remote)


async def run_trv_poll_loop() -> None:
    if not settings.shelly_gateway_host or not trv_rooms():
        logger.info("No Shelly gateway or TRVs configured; heating control off")
        return
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        while True:
            try:
                await _poll(client)
            except TrvError as e:
                logger.warning("TRV poll failed: %s", e)
            except Exception:
                logger.exception("TRV poll crashed")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def set_target(room: str, target_c: float) -> None:
    mac = next((m for m, r in trv_rooms().items() if r == room), None)
    valve_id = _valve_ids.get(mac) if mac else None
    if valve_id is None or not settings.shelly_gateway_host:
        raise KeyError(room)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        await _rpc(client, "BluTrv.Call", {
            "id": valve_id,
            "method": "TRV.SetTarget",
            "params": {"id": 0, "target_C": target_c},
        })
    _written[room] = (target_c, time.time())
    if room in _states:
        _states[room] = {**_states[room], "target_temperature": target_c}
    logger.info("TRV %s set to %.1f °C", room, target_c)
