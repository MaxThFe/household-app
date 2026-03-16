import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db
from app.routers import calendar, meals, recipes, shopping
from app.services.ics_sync import run_ics_sync_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    sync_task = asyncio.create_task(run_ics_sync_loop())
    yield
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="HomeTogether API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recipes.router, prefix="/api/v1")
app.include_router(meals.router, prefix="/api/v1")
app.include_router(shopping.router, prefix="/api/v1")
app.include_router(calendar.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
