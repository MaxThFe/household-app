"""Tests for turning the gateway's BLU TRV status into a room's thermostat.

Payloads are trimmed copies of what a BLU Gateway Gen3 returned on the LAN.
"""

import time

import pytest

from app.services import shelly_trv

MAC = "F844771D05A0"

LINK = {
    "id": 201, "rssi": -62, "battery": 81, "packet_id": 49,
    "last_updated_ts": time.time() - 30, "paired": True, "rpc": True,
}
REMOTE = {
    "v": 18,
    "ts": time.time() - 600,
    "status": {
        "temperature:0": {"id": 0, "tC": 19.05, "errors": []},
        "trv:0": {"id": 0, "pos": 100, "current_C": 19.05, "target_C": 20.0, "errors": []},
    },
}


@pytest.fixture(autouse=True)
def no_writes():
    shelly_trv._written.clear()
    yield
    shelly_trv._written.clear()


def test_reads_the_cached_valve_status():
    state = shelly_trv._state("Bedroom", MAC, LINK, REMOTE)
    assert state["current_temperature"] == 19.05
    assert state["target_temperature"] == 20.0
    assert state["valve_position"] == 100
    assert state["battery"] == 81
    assert state["stale"] is False
    assert state["reachable"] is True


def test_a_write_newer_than_the_cache_wins():
    shelly_trv._written["Bedroom"] = (22.5, time.time())
    assert shelly_trv._state("Bedroom", MAC, LINK, REMOTE)["target_temperature"] == 22.5


def test_the_cache_wins_once_the_valve_has_reported_since():
    shelly_trv._written["Bedroom"] = (22.5, REMOTE["ts"] - 60)
    assert shelly_trv._state("Bedroom", MAC, LINK, REMOTE)["target_temperature"] == 20.0


def test_connect_failed_marks_the_valve_unreachable():
    link = {**LINK, "errors": ["connect_failed"]}
    assert shelly_trv._state("Bedroom", MAC, link, REMOTE)["reachable"] is False


def test_silent_valve_is_stale():
    link = {**LINK, "last_updated_ts": time.time() - 3 * 3600}
    assert shelly_trv._state("Bedroom", MAC, link, REMOTE)["stale"] is True
