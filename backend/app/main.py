import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.routers import calendar, houseplants, meals, recipes, shopping, vacuum
from app.services.ics_sync import run_ics_sync_loop
from app.services.vacuum_scheduler import run_vacuum_scheduler_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    sync_task = asyncio.create_task(run_ics_sync_loop())
    vacuum_task = asyncio.create_task(run_vacuum_scheduler_loop())
    yield
    sync_task.cancel()
    vacuum_task.cancel()
    for task in (sync_task, vacuum_task):
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="OurHome API", version="0.1.0", lifespan=lifespan)

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
app.include_router(houseplants.router, prefix="/api/v1")
app.include_router(vacuum.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/config")
async def config():
    return {"user1_name": settings.user1_name, "user2_name": settings.user2_name}
