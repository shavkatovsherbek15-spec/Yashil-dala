from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.i18n import LANGS, normalize_lang, translate
from app.regions import region_name
from app.services import cart

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def format_number(value: int | None) -> str:
    """45000 -> "45 000" (bo'linmas probel); None/0 -> [narx]."""
    return f"{value:,}".replace(",", "\u00a0") if value else "[narx]"


templates.env.filters["num"] = format_number

CATEGORY_STYLES = {
    # slug: (fon, matn, ikonka)
    "ogit": ("#E3EFE5", "#1E5B3A", "sprout"),
    "himoya": ("#FBF0D9", "#7A4A06", "shield"),
    "uy": ("#E5ECF3", "#24486B", "house"),
}


def get_lang(request: Request) -> str:
    return normalize_lang(request.cookies.get("lang"), get_settings().default_lang)


def safe_next(url: str, default: str = "/") -> str:
    """Faqat sayt ichidagi yo'lga qaytarish (open redirect'dan himoya)."""
    if url.startswith("/") and not url.startswith(("//", "/\\")):
        return url
    return default


def money(value: int | None, lang: str) -> str:
    if value is None:
        return f"{translate(lang, 'price_placeholder')} {translate(lang, 'currency')}"
    return f"{value:,}".replace(",", " ") + f" {translate(lang, 'currency')}"


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    lang = get_lang(request)

    def t(key: str, **kwargs: object) -> str:
        return translate(lang, key, **kwargs)

    def url_with(**params: object) -> str:
        """Joriy query parametrlarini o'zgartirib URL qaytaradi (None — o'chiradi)."""
        query = dict(request.query_params)
        for k, v in params.items():
            if v is None or v == "":
                query.pop(k, None)
            else:
                query[k] = str(v)
        return request.url.path + (f"?{urlencode(query)}" if query else "")

    ctx = {
        "lang": lang,
        "langs": LANGS,
        "t": t,
        "money": lambda v: money(v, lang),
        "url_with": url_with,
        "settings": get_settings(),
        "cart_count": cart.count(request),
        "cat_style": lambda slug: CATEGORY_STYLES.get(slug, CATEGORY_STYLES["ogit"]),
        "current_path": request.url.path,
        "now_year": date.today().year,
        "region_name": region_name,
    }
    ctx.update(context or {})
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
