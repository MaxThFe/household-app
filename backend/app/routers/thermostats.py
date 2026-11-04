from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_auth
from app.models.thermostat import ThermostatState, ThermostatTarget
from app.services.shelly_trv import TrvError, get_thermostats, set_target

router = APIRouter(prefix="/thermostats", tags=["thermostats"])


@router.get("", response_model=list[ThermostatState])
async def list_thermostats():
    return get_thermostats()


@router.put("/{room}/target", status_code=204)
async def put_target(room: str, body: ThermostatTarget, _=Depends(require_auth)):
    try:
        await set_target(room, body.target_c)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No thermostat in {room}")
    except TrvError as e:
        raise HTTPException(status_code=504 if e.timeout else 502, detail=str(e))
