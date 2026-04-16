from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.api.studio_routes import router as studio_router
from app.core.config import get_settings
from app.db.session import init_db
from app.ui.routes import router as ui_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manage startup and shutdown for the LeadBot Studio API."""
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()
    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.include_router(ui_router)
    application.include_router(router)
    application.include_router(studio_router)
    return application


app = create_app()
