from pydantic import BaseModel, Field

from app.services.shelly_trv import MAX_TARGET_C, MIN_TARGET_C


class ThermostatState(BaseModel):
    room: str
    mac: str
    # The valve's own reading, at the radiator — warmer than the room sensor.
    current_temperature: float | None = None
    target_temperature: float | None = None
    valve_position: int | None = None  # % open
    battery: int | None = None
    last_seen: str | None = None
    stale: bool
    # False while the gateway cannot connect to the valve to change it.
    reachable: bool


class ThermostatTarget(BaseModel):
    target_c: float = Field(ge=MIN_TARGET_C, le=MAX_TARGET_C)
