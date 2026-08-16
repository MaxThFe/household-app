from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.timeseries import get_timeseries_db
from app.models.sensor import SensorHistory, SensorReading, SensorSeriesInfo
from app.services.ble_sensors import get_readings
from app.services.sensor_history import (
    DEFAULT_MAX_POINTS,
    MAX_POINTS_CEILING,
    fetch_history,
    list_series,
)

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.get("", response_model=list[SensorReading])
async def list_sensors():
    return get_readings()


@router.get("/series", response_model=list[SensorSeriesInfo])
async def sensor_series(db: aiosqlite.Connection = Depends(get_timeseries_db)):
    return await list_series(db)


def _epoch(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


@router.get("/history", response_model=list[SensorHistory])
async def sensor_history(
    start: datetime,
    end: datetime,
    series: list[str] = Query(..., description="room:metric, repeatable"),
    max_points: int = Query(DEFAULT_MAX_POINTS, ge=1, le=MAX_POINTS_CEILING),
    db: aiosqlite.Connection = Depends(get_timeseries_db),
):
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start")

    result = []
    for item in series:
        room, _, metric = item.partition(":")
        if not room or not metric:
            raise HTTPException(status_code=400, detail=f"bad series: {item}")
        result.append(
            await fetch_history(db, room, metric, _epoch(start), _epoch(end), max_points)
        )
    return result
