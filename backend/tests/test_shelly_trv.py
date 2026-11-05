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


@pytest.fixture
def no_pushes():
    shelly_trv._pushed.clear()
    shelly_trv._push_failed.clear()
    yield
    shelly_trv._pushed.clear()
    shelly_trv._push_failed.clear()


def test_first_room_reading_is_pushed(no_pushes):
    assert shelly_trv._push_due("Bedroom", 19.4, time.time()) is True


def test_unchanged_reading_is_not_pushed_again(no_pushes):
    now = time.time()
    shelly_trv._pushed["Bedroom"] = (19.4, now - 60)
    assert shelly_trv._push_due("Bedroom", 19.45, now) is False


def test_moved_reading_is_pushed(no_pushes):
    now = time.time()
    shelly_trv._pushed["Bedroom"] = (19.4, now - 60)
    assert shelly_trv._push_due("Bedroom", 19.5, now) is True


def test_old_push_is_refreshed(no_pushes):
    now = time.time()
    shelly_trv._pushed["Bedroom"] = (19.4, now - shelly_trv.EXTERNAL_REFRESH_SECONDS)
    assert shelly_trv._push_due("Bedroom", 19.4, now) is True


def test_failed_push_backs_off(no_pushes):
    now = time.time()
    shelly_trv._push_failed["Bedroom"] = now - 60
    assert shelly_trv._push_due("Bedroom", 19.4, now) is False


def test_state_shows_room_sensor_while_fed(no_pushes):
    shelly_trv._pushed["Bedroom"] = (18.6, time.time() - 60)
    state = shelly_trv._state("Bedroom", MAC, LINK, REMOTE)
    assert state["regulated_by"] == "room_sensor"
    assert state["room_temperature"] == 18.6


def test_state_falls_back_to_valve_when_feed_stops(no_pushes):
    shelly_trv._pushed["Bedroom"] = (18.6, time.time() - 3 * shelly_trv.EXTERNAL_REFRESH_SECONDS)
    state = shelly_trv._state("Bedroom", MAC, LINK, REMOTE)
    assert state["regulated_by"] == "valve"
    assert state["room_temperature"] is None


class FakeClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, json):
        self.calls.append(json["params"])

        class Res:
            def json(self):
                return {"id": 1, "result": None}

        return Res()


def _run_push(monkeypatch, reading):
    monkeypatch.setattr(shelly_trv, "_CALL_GAP_SECONDS", 0)
    monkeypatch.setattr(shelly_trv, "_room_temperature", lambda room: reading)
    client = FakeClient()
    import asyncio
    asyncio.run(shelly_trv._push_room_temperature(client, "Bedroom", 200))
    return client.calls


def test_pushes_room_reading_through_the_gateway(monkeypatch, no_pushes):
    calls = _run_push(monkeypatch, 18.6)
    assert calls == [{"id": 200, "method": "TRV.SetExternalTemperature", "params": {"id": 0, "t_C": 18.6}}]
    assert shelly_trv._pushed["Bedroom"][0] == 18.6


def test_quiet_sensor_hands_the_valve_back_its_own(monkeypatch, no_pushes):
    shelly_trv._pushed["Bedroom"] = (18.6, time.time() - 60)
    calls = _run_push(monkeypatch, None)
    assert calls == [{"id": 200, "method": "TRV.SetExternalTemperature", "params": {"id": 0}}]
    assert "Bedroom" not in shelly_trv._pushed


def test_quiet_sensor_never_fed_sends_nothing(monkeypatch, no_pushes):
    assert _run_push(monkeypatch, None) == []


class FlakyGateway:
    """Answers polls from canned payloads; every TRV write times out."""

    def __init__(self, link):
        self.link = link
        self.writes = 0

    async def post(self, url, json):
        method, params = json["method"], json["params"]
        if method == "BluTrv.Call":
            self.writes += 1
            result = {"error": {"code": 504, "message": "Deadline exceeded"}}
        elif method == "BluTrv.GetStatus":
            result = {"result": self.link}
        elif method == "BluTrv.GetRemoteStatus":
            result = {"result": REMOTE}
        else:
            raise AssertionError(method)

        class Res:
            def json(self):
                return {"id": 1, **result}

        return Res()


def test_unreachable_valve_is_still_tried_then_backs_off(monkeypatch, no_pushes):
    import asyncio
    monkeypatch.setattr(shelly_trv, "_CALL_GAP_SECONDS", 0)
    monkeypatch.setattr(shelly_trv, "trv_rooms", lambda: {MAC: "Bedroom"})
    monkeypatch.setattr(shelly_trv, "_room_temperature", lambda room: 18.6)
    monkeypatch.setitem(shelly_trv._valve_ids, MAC, 200)
    gateway = FlakyGateway({**LINK, "errors": ["connect_failed"]})

    asyncio.run(shelly_trv._poll(gateway))
    assert gateway.writes == 1
    assert "Bedroom" in shelly_trv._push_failed

    asyncio.run(shelly_trv._poll(gateway))
    assert gateway.writes == 1  # backing off, no second attempt yet
