import json
from functools import lru_cache
from pathlib import Path

LANGS = ("uz", "ru")
LOCALES_DIR = Path(__file__).parent / "locales"


@lru_cache
def _load(lang: str) -> dict[str, str]:
    return json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def translate(lang: str, key: str, **kwargs: object) -> str:
    text = _load(lang).get(key) or _load("uz").get(key) or key
    return text.format(**kwargs) if kwargs else text


def normalize_lang(value: str | None, default: str = "uz") -> str:
    return value if value in LANGS else default
