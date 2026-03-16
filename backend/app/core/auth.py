from fastapi import Header, HTTPException

from app.core.config import settings


async def require_auth(x_user: str = Header(...)) -> str:
    if x_user in (settings.user1_name, settings.user2_name):
        return x_user
    raise HTTPException(status_code=401, detail="Unknown user")
