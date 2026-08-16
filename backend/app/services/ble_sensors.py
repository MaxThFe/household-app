"""Passive BLE listener for the Xiaomi LYWSD03MMC sensors.

The sensors run custom firmware that broadcasts unencrypted BTHome v2
advertisements (16-bit service UUID 0xFCD2), so no pairing, cloud account or
bind key is involved — we just listen and decode whatever flies past.

Readings are kept in memory only: the newest advertisement per sensor wins and
nothing is persisted.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)

BTHOME_UUID = "0000fcd2-0000-1000-8000-00805f9b34fb"

# BTHome v2 measurement objects we care about, plus the ones we merely need to
# know the width of so we can step over them. (object id -> (name, length,
# signed, factor)); a name of None means "skip this value".
_OBJECTS: dict[int, tuple[str | None, int, bool, float]] = {
    0x00: (None, 1, False, 1),           # packet id
    0x01: ("battery", 1, False, 1),      # %
    0x02: ("temperature", 2, True, 0.01),  # °C
    0x03: ("humidity", 2, False, 0.01),  # %
    0x05: (None, 3, False, 1),           # illuminance
    0x0C: ("voltage", 2, False, 0.001),  # V
    0x10: (None, 1, False, 1),           # binary: power
    0x11: (None, 1, False, 1),           # binary: opening
    0x2E: ("humidity", 1, False, 1),     # coarse humidity, %
    0x45: ("temperature", 2, True, 0.1),  # coarse temperature, °C
}


def sensor_rooms() -> dict[str, str]:
    """Configured MAC (upper case) -> room name, in display order."""
    pairs = (
        (settings.sensor_living_room_mac, "Living room"),
        (settings.sensor_bedroom_mac, "Bedroom"),
        (settings.sensor_kitchen_mac, "Kitchen"),
    )
    return {mac.strip().upper(): room for mac, room in pairs if mac.strip()}


def decode_bthome_v2(payload: bytes) -> dict[str, float] | None:
    """Decode an unencrypted BTHome v2 service-data payload.

    Returns the measurements found, or None if the payload is not something we
    can read (wrong version, encrypted, or malformed).
    """
    if len(payload) < 2:
        return None

    device_info = payload[0]
    if device_info >> 5 != 2:  # BTHome version in the top 3 bits
        return None
    if device_info & 0x01:  # encryption flag
        return None

    values: dict[str, float] = {}
    i = 1
    while i < len(payload):
        obj = _OBJECTS.get(payload[i])
        if obj is None:
            # Unknown object id: without its width we can't find the next one.
            break
        name, length, signed, factor = obj
        i += 1
        if i + length > len(payload):
            break
        if name is not None:
            raw = int.from_bytes(payload[i : i + length], "little", signed=signed)
            values[name] = round(raw * factor, 2)
        i += length

    return values or None


def _on_advertisement(device, advertisement_data) -> None:
    rooms = sensor_rooms()
    mac = device.address.upper()
    if mac not in rooms:
        return

    payload = advertisement_data.service_data.get(BTHOME_UUID)
    if not payload:
        return

    values = decode_bthome_v2(bytes(payload))
    if not values:
        return

    # The sensors alternate between a temperature/humidity packet and a
    # battery-voltage one, so merge into whatever we already hold rather than
    # replacing it and blanking half the fields.
    reading = _readings.setdefault(mac, {})
    reading.update(values)
    reading["rssi"] = advertisement_data.rssi
    reading["last_seen"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


_readings: dict[str, dict] = {}


def get_readings() -> list[dict]:
    """Latest reading per configured sensor, in display order."""
    now = datetime.now(timezone.utc)
    stale_after = settings.sensor_stale_after_minutes * 60

    result = []
    for mac, room in sensor_rooms().items():
        reading = _readings.get(mac, {})
        last_seen = reading.get("last_seen")
        stale = True
        if last_seen:
            age = (now - datetime.fromisoformat(last_seen)).total_seconds()
            stale = age > stale_after
        result.append(
            {
                "room": room,
                "mac": mac,
                "temperature": reading.get("temperature"),
                "humidity": reading.get("humidity"),
                "battery": int(reading["battery"]) if "battery" in reading else None,
                "voltage": reading.get("voltage"),
                "rssi": reading.get("rssi"),
                "last_seen": last_seen,
                "stale": stale,
            }
        )
    return result


async def _scan(passive: bool) -> None:
    from bleak import BleakScanner

    # No service_uuids filter: the sensors advertise service *data* for 0xFCD2
    # without listing the UUID itself, so BlueZ's filter would drop them. We
    # match on MAC in the callback instead.
    kwargs: dict = {}
    if passive:
        from bleak.assigned_numbers import AdvertisementDataType

        try:
            from bleak.args.bluez import BlueZScannerArgs, OrPattern
        except ImportError:  # bleak < 1.0
            from bleak.backends.bluezdbus.advertisement_monitor import OrPattern
            from bleak.backends.bluezdbus.scanner import BlueZScannerArgs

        kwargs["scanning_mode"] = "passive"
        kwargs["bluez"] = BlueZScannerArgs(
            or_patterns=[
                OrPattern(0, AdvertisementDataType.SERVICE_DATA_UUID16, b"\xd2\xfc")
            ]
        )

    async with BleakScanner(_on_advertisement, **kwargs):
        logger.info(
            "BLE sensor scanner running (%s) for %s",
            "passive" if passive else "active",
            ", ".join(sensor_rooms().values()),
        )
        while True:
            await asyncio.sleep(3600)


async def run_ble_sensor_loop() -> None:
    if not sensor_rooms():
        logger.info("No BLE sensors configured, scanner disabled")
        return

    # Passive scanning avoids waking the sensors with scan requests, but needs
    # a BlueZ new enough for advertisement monitors — fall back if it fails.
    passive = True
    while True:
        try:
            await _scan(passive)
        except asyncio.CancelledError:
            raise
        except Exception:
            if passive:
                logger.warning(
                    "Passive BLE scan unavailable, falling back to active scanning",
                    exc_info=True,
                )
                passive = False
                continue
            logger.exception("BLE scanner stopped, retrying in 30s")
            await asyncio.sleep(30)
