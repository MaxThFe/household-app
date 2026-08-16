from fastapi import APIRouter

from app.models.sensor import SensorReading
from app.services.ble_sensors import get_readings

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.get("", response_model=list[SensorReading])
async def list_sensors():
    return get_readings()
