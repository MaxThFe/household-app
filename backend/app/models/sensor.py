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


class SensorSeries(BaseModel):
    room: str
    metric: str
    unit: str


class SensorHistory(SensorSeries):
    # True when the range held more points than asked for and they were averaged
    # into buckets; the stored rows are untouched either way.
    bucketed: bool
    points: list[list[float]]
