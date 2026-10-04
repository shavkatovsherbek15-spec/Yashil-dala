REGIONS: list[tuple[str, str, str]] = [
    ("toshkent-sh", "Toshkent shahri", "г. Ташкент"),
    ("toshkent", "Toshkent viloyati", "Ташкентская область"),
    ("andijon", "Andijon viloyati", "Андижанская область"),
    ("buxoro", "Buxoro viloyati", "Бухарская область"),
    ("fargona", "Farg‘ona viloyati", "Ферганская область"),
    ("jizzax", "Jizzax viloyati", "Джизакская область"),
    ("xorazm", "Xorazm viloyati", "Хорезмская область"),
    ("namangan", "Namangan viloyati", "Наманганская область"),
    ("navoiy", "Navoiy viloyati", "Навоийская область"),
    ("qashqadaryo", "Qashqadaryo viloyati", "Кашкадарьинская область"),
    ("samarqand", "Samarqand viloyati", "Самаркандская область"),
    ("sirdaryo", "Sirdaryo viloyati", "Сырдарьинская область"),
    ("surxondaryo", "Surxondaryo viloyati", "Сурхандарьинская область"),
    ("qoraqalpogiston", "Qoraqalpog‘iston Respublikasi", "Республика Каракалпакстан"),
]

_BY_SLUG = {slug: (uz, ru) for slug, uz, ru in REGIONS}


def region_name(slug: str, lang: str) -> str:
    uz, ru = _BY_SLUG.get(slug, (slug, slug))
    return ru if lang == "ru" else uz


def is_region(slug: str) -> bool:
    return slug in _BY_SLUG
