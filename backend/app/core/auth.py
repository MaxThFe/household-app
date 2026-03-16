from fastapi import Header, HTTPException

from app.core.config import settings


async def require_auth(x_user_pin: str = Header(...)) -> str:
    if x_user_pin == settings.user1_pin:
        return settings.user1_name
    if x_user_pin == settings.user2_pin:
        return settings.user2_name
    raise HTTPException(status_code=401, detail="Invalid PIN")
