"""Mahsulot rasmlarini saqlash (media_dir, /media/... manzili)."""

import secrets
from pathlib import Path

from app.config import get_settings

MEDIA_URL = "/media/"


def media_root() -> Path:
    root = Path(get_settings().media_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def detect_image(head: bytes) -> str | None:
    """Fayl turini kengaytmaga emas, ichidagi baytlarga qarab aniqlash."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def save_image(product_id: int, content: bytes) -> str:
    """Rasmni saqlaydi va URL qaytaradi. Noto'g'ri fayl — ValueError."""
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValueError(f"Rasm {get_settings().max_upload_mb} MB dan katta bo‘lmasin.")
    ext = detect_image(content[:16])
    if ext is None:
        raise ValueError("Faqat JPG, PNG yoki WEBP rasm yuklash mumkin.")
    name = f"p{product_id}-{secrets.token_hex(8)}.{ext}"
    (media_root() / name).write_bytes(content)
    return MEDIA_URL + name


def delete_image(url: str) -> None:
    if not url.startswith(MEDIA_URL):
        return
    root = media_root()
    path = (root / url.removeprefix(MEDIA_URL)).resolve()
    if path.parent == root and path.is_file():
        path.unlink()
