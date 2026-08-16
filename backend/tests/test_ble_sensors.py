"""Tests for the BTHome v2 advertisement decoder.

Payloads here are synthetic, hand-built to the BTHome v2 spec.
"""

from app.services.ble_sensors import decode_bthome_v2

# device info 0x40 (v2, unencrypted), packet id, battery 50%,
# temperature 21.50 °C, humidity 45.00 %
FULL_READING = bytes.fromhex("4000010132026608039411")
# The alternating packet: packet id, voltage 3.000 V, then two binary objects
# the decoder should step over without tripping.
VOLTAGE_READING = bytes.fromhex("4000010cb80b10001101")


def test_decodes_temperature_humidity_and_battery():
    assert decode_bthome_v2(FULL_READING) == {
        "battery": 50,
        "temperature": 21.5,
        "humidity": 45.0,
    }


def test_decodes_negative_temperature():
    # -5.00 °C arrives as a signed little-endian 0xFE0C.
    assert decode_bthome_v2(bytes.fromhex("40020cfe"))["temperature"] == -5.0


def test_decodes_voltage_and_skips_binary_objects():
    assert decode_bthome_v2(VOLTAGE_READING) == {"voltage": 3.0}


def test_rejects_encrypted_payload():
    encrypted = bytes([0x41]) + FULL_READING[1:]
    assert decode_bthome_v2(encrypted) is None


def test_rejects_bthome_v1():
    v1 = bytes([0x20]) + FULL_READING[1:]
    assert decode_bthome_v2(v1) is None


def test_rejects_empty_payload():
    assert decode_bthome_v2(b"") is None
    assert decode_bthome_v2(b"\x40") is None


def test_stops_cleanly_on_truncated_measurement():
    # Battery reads fine; the temperature object is cut short and dropped.
    assert decode_bthome_v2(bytes.fromhex("4001320266")) == {"battery": 50}


def test_returns_none_when_nothing_decodable():
    # Device info only followed by an unknown object id.
    assert decode_bthome_v2(bytes.fromhex("40ff00")) is None
