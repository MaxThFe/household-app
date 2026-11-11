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


class SensorSeriesInfo(SensorSeries):
    # Extent of the stored history, so the app can open on a range that has
    # data instead of an empty 24 h window. None until the first sample lands.
    first_ts: int | None = None
    last_ts: int | None = None


class SensorHistory(SensorSeries):
    # True when the range held more points than asked for and they were averaged
    # into buckets; the stored rows are untouched either way.
    bucketed: bool
    points: list[list[float]]
