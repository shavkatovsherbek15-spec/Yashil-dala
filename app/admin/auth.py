"""Admin kirishi: parol xeshi (scrypt), sessiya, CSRF va urinishlar cheklovi."""

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.db import get_db
from app.models import AdminUser

SESSION_KEY = "admin_id"
SESSION_SEEN = "admin_seen"
IDLE_TIMEOUT = 60 * 60 * 12  # 12 soat harakatsizlikdan keyin qayta kirish

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        check = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), dklen=32, n=int(n), r=int(r), p=int(p)
        )
    except ValueError:
        return False
    return secrets.compare_digest(check.hex(), digest)


# --- Noto'g'ri urinishlar: IP bo'yicha 15 daqiqada 5 ta (bitta jarayon uchun yetarli) ---
_WINDOW = 15 * 60
_MAX_FAILS = 5
_fails: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def too_many_attempts(request: Request) -> bool:
    q = _fails[_client_ip(request)]
    now = time.monotonic()
    while q and now - q[0] > _WINDOW:
        q.popleft()
    return len(q) >= _MAX_FAILS


def record_failure(request: Request) -> None:
    _fails[_client_ip(request)].append(time.monotonic())


def reset_failures(request: Request) -> None:
    _fails.pop(_client_ip(request), None)


def login(request: Request, db: Session, user: AdminUser) -> None:
    request.session.pop(SESSION_KEY, None)
    request.session[SESSION_KEY] = user.id
    request.session[SESSION_SEEN] = int(time.time())
    request.session["csrf"] = secrets.token_urlsafe(32)  # kirgandan keyin yangi token
    user.last_login_at = datetime.now(UTC)
    db.commit()


def logout(request: Request) -> None:
    for key in (SESSION_KEY, SESSION_SEEN, "csrf"):
        request.session.pop(key, None)


class LoginRequired(Exception):
    """main.py dagi handler /admin/kirish ga yo'naltiradi."""


def current_admin(request: Request, db: Annotated[Session, Depends(get_db)]) -> AdminUser:
    admin_id = request.session.get(SESSION_KEY)
    seen = request.session.get(SESSION_SEEN, 0)
    if not admin_id or time.time() - seen > IDLE_TIMEOUT:
        logout(request)
        raise LoginRequired
    user = db.get(AdminUser, admin_id)
    if user is None or not user.is_active:
        logout(request)
        raise LoginRequired
    request.session[SESSION_SEEN] = int(time.time())
    return user


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = request.session["csrf"] = secrets.token_urlsafe(32)
    return token


async def checked_form(request: Request) -> FormData:
    """POST formani o'qiydi va CSRF tokenini tekshiradi."""
    form = await request.form()
    sent = form.get("csrf")
    expected = request.session.get("csrf")
    if not expected or not isinstance(sent, str) or not secrets.compare_digest(sent, expected):
        raise HTTPException(400, "CSRF token noto‘g‘ri. Sahifani yangilab, qayta urinib ko‘ring.")
    return form


Admin = Annotated[AdminUser, Depends(current_admin)]
