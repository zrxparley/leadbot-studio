from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["leadbot-console"])
CONSOLE_HTML_PATH = Path(__file__).with_name("console.html")


@router.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse(url="/studio/console", status_code=307)


@router.get("/studio/console", response_class=HTMLResponse, include_in_schema=False)
def studio_console() -> str:
    return CONSOLE_HTML_PATH.read_text(encoding="utf-8")
