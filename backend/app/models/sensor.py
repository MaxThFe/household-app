from pydantic import BaseModel


class SensorReading(BaseModel):
    room: str
    mac: str
    temperature: float | None = None
    humidity: float | None = None
    battery: int | None = None
    voltage: float | None = None
    rssi: int | None = None
    last_seen: str | None = None
    stale: bool
