import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.admin import media
from app.admin.auth import LoginRequired
from app.admin.routes import router as admin_router
from app.config import get_settings
from app.routers import pages, shop, telegram
from app.web import render

logging.basicConfig(level=logging.INFO)

settings = get_settings()
app = FastAPI(title=settings.shop_name, docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="yd_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=settings.session_https_only,
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.mount("/media", StaticFiles(directory=media.media_root()), name="media")

app.include_router(pages.router)
app.include_router(shop.router)
app.include_router(telegram.router)
app.include_router(admin_router)


@app.exception_handler(LoginRequired)
async def login_required(request: Request, exc: LoginRequired):
    next_url = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse(f"/admin/kirish?next={quote(next_url)}", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return render(request, "404.html", status_code=404)
    return await http_exception_handler(request, exc)
