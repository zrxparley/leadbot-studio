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


@router.get("/studio/chat", response_class=HTMLResponse, include_in_schema=False)
def studio_chat() -> str:
    return CONSOLE_HTML_PATH.read_text(encoding="utf-8")


@router.get("/studio/agents-config", response_class=HTMLResponse, include_in_schema=False)
def studio_agents_config() -> str:
    return CONSOLE_HTML_PATH.read_text(encoding="utf-8")


@router.get("/studio/workflows", response_class=HTMLResponse, include_in_schema=False)
def studio_workflows() -> str:
    return CONSOLE_HTML_PATH.read_text(encoding="utf-8")


@router.get("/studio/proposals", response_class=HTMLResponse, include_in_schema=False)
def studio_proposals() -> str:
    return CONSOLE_HTML_PATH.read_text(encoding="utf-8")
