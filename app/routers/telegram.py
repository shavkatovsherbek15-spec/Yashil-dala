import secrets

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.config import get_settings
from app.services.telegram import handle_update

router = APIRouter()


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    background: BackgroundTasks,
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    expected = get_settings().telegram_webhook_secret
    if not expected or not secrets.compare_digest(x_telegram_bot_api_secret_token, expected):
        raise HTTPException(403)
    background.add_task(handle_update, await request.json())
    return {"ok": True}
