"""Namunaviy ma'lumotlar (design/Tanlash.dc.html dagi ro'yxat asosida).

Ishlatish:
    python -m scripts.seed           # baza bo'sh bo'lsa to'ldiradi
    python -m scripts.seed --reset   # katalog jadvallarini tozalab, qayta to'ldiradi

Narx, doza, guvohnoma raqami hozircha bo'sh — saytda [narx], [doza] ko'rinadi.
"""

import sys

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    Category,
    Crop,
    CropProblem,
    Problem,
    ProblemType,
    Product,
    ProductUsage,
    ProductVariant,
)

CATEGORIES = [
    # slug, name_uz, name_ru, short_uz, short_ru, desc_uz, desc_ru
    ("ogit", "O‘g‘itlar va stimulyatorlar", "Удобрения и стимуляторы", "O‘g‘it", "Удобрения",
     "Oziqlantirish, tez o‘sish, mo‘l hosil", "Подкормка, быстрый рост, богатый урожай"),
    ("himoya", "O‘simlik himoyasi", "Защита растений", "Himoya", "Защита",
     "Zararkunanda va kasalliklarga qarshi", "От вредителей и болезней"),
    ("uy", "Uy uchun vositalar", "Средства для дома", "Uy uchun", "Для дома",
     "Tarakan, chumoli va boshqa hasharotlarga qarshi", "От тараканов, муравьёв и других насекомых"),
]

CROPS = [
    # slug, uz, ru, rang
    ("pomidor", "Pomidor", "Помидор", "#F06A52"),
    ("bodring", "Bodring", "Огурец", "#9BD27E"),
    ("olma", "Olma", "Яблоня", "#E5535C"),
    ("uzum", "Uzum", "Виноград", "#B88AD0"),
    ("kartoshka", "Kartoshka", "Картофель", "#D9B27A"),
    ("goza", "G‘o‘za", "Хлопчатник", "#E6DCC0"),
    ("piyoz", "Piyoz", "Лук", "#E9A65A"),
    ("uy", "Uy-joy", "Дом", "#A9C3DB"),
]

P = ProblemType
PROBLEMS = [
    ("shira", "Shira", "Тля", P.pest),
    ("trips", "Trips", "Трипс", P.pest),
    ("kana", "O‘rgimchakkana", "Паутинный клещ", P.pest),
    ("qurt", "Olma qurti", "Яблонная плодожорка", P.pest),
    ("kolorado", "Kolorado qo‘ng‘izi", "Колорадский жук", P.pest),
    ("unshudring", "Un-shudring", "Мучнистая роса", P.disease),
    ("fitoftoroz", "Fitoftoroz", "Фитофтороз", P.disease),
    ("chirish", "Kulrang chirish", "Серая гниль", P.disease),
    ("sekin", "Sekin o‘sish", "Медленный рост", P.nutrition),
    ("sargayish", "Barglar sarg‘ayishi", "Пожелтение листьев", P.nutrition),
    ("gul", "Gul va tugun kam", "Мало цветков и завязей", P.nutrition),
    ("tarakan", "Tarakan", "Тараканы", P.household),
    ("chumoli", "Chumoli", "Муравьи", P.household),
]

CROP_PROBLEMS = {
    "pomidor": ["shira", "trips", "kana", "fitoftoroz", "unshudring", "sekin", "sargayish", "gul"],
    "bodring": ["shira", "trips", "kana", "unshudring", "sekin", "sargayish"],
    "olma": ["shira", "kana", "qurt", "unshudring", "sekin", "gul"],
    "uzum": ["shira", "kana", "unshudring", "chirish", "sekin"],
    "kartoshka": ["kolorado", "fitoftoroz", "sekin", "sargayish"],
    "goza": ["kana", "sekin", "sargayish"],
    "piyoz": ["sekin", "sargayish"],
    "uy": ["tarakan", "chumoli"],
}

FIELD_CROPS = ["pomidor", "bodring", "olma", "uzum", "kartoshka", "goza", "piyoz"]

SPRAY_USAGE_UZ = """Jadvaldagi dozani o‘lchab, toza suvda eriting.
Tayyor eritmani shu kunning o‘zida ishlating.
Shamolsiz kunda, ertalab yoki kechqurun seping.
Hosil yig‘ishdan {days} kun oldin ishlov berishni to‘xtating."""
SPRAY_USAGE_RU = """Отмерьте дозу из таблицы и растворите в чистой воде.
Используйте готовый раствор в тот же день.
Опрыскивайте в безветренную погоду утром или вечером.
Прекратите обработку за {days} дн. до сбора урожая."""
SPRAY_SAFETY_UZ = """Qo‘lqop, niqob va ko‘zoynakda ishlang.
Bolalar va uy hayvonlaridan uzoqda saqlang.
Oziq-ovqat va ichimliklar yonida saqlamang.
Asalarilar faol paytda sepmang."""
SPRAY_SAFETY_RU = """Работайте в перчатках, маске и очках.
Храните в недоступном для детей и животных месте.
Не храните рядом с продуктами и напитками.
Не опрыскивайте во время активного лёта пчёл."""
FERT_USAGE_UZ = """Jadvaldagi dozani o‘lchab, suvda eriting.
Ildiz ostiga quying yoki barg orqali seping.
Har 10–14 kunda takrorlang."""
FERT_USAGE_RU = """Отмерьте дозу из таблицы и растворите в воде.
Полейте под корень или опрыскайте по листу.
Повторяйте каждые 10–14 дней."""
FERT_SAFETY_UZ = """Bolalardan uzoqda saqlang.
Quruq va salqin joyda saqlang."""
FERT_SAFETY_RU = """Храните в недоступном для детей месте.
Храните в сухом прохладном месте."""
HOME_USAGE_UZ = """Gelni hasharotlar yuradigan joylarga nuqta qilib surting.
Nuqtalar orasi 10–20 sm bo‘lsin.
Gel qurisa, yangisini surting."""
HOME_USAGE_RU = """Нанесите гель точками в местах передвижения насекомых.
Расстояние между точками 10–20 см.
Обновляйте, когда гель высохнет."""
HOME_SAFETY_UZ = """Bolalar va uy hayvonlari yeta olmaydigan joyga surting.
Oziq-ovqat tegadigan yuzalarga surtmang.
Ishdan so‘ng qo‘lingizni sovunlab yuving."""
HOME_SAFETY_RU = """Наносите в местах, недоступных детям и животным.
Не наносите на поверхности, контактирующие с едой.
После работы вымойте руки с мылом."""

PRODUCTS = [
    {
        "slug": "shiraga-qarshi-insektitsid", "cat": "himoya", "shape": "bottle", "popular": True,
        "name": ("Shiraga qarshi insektitsid", "Инсектицид от тли"),
        "kind": ("Insektitsid", "Инсектицид"),
        "desc": ("Sabzavot va mevali bog‘larda shira va tripslarga qarshi qo‘llanadi. Quyida ruxsat etilgan ekinlar va dozasi berilgan.",
                 "Применяется против тли и трипса на овощах и в плодовых садах. Ниже — разрешённые культуры и доза."),
        "packs": ["250 ml", "1 L", "5 L"],
        "usages": {"pomidor": ["shira", "trips"], "bodring": ["shira", "trips"], "olma": ["shira"], "uzum": ["shira"]},
        "texts": "spray",
    },
    {
        "slug": "osish-stimulyatori", "cat": "ogit", "shape": "bottle", "popular": True,
        "name": ("O‘sish stimulyatori", "Стимулятор роста"),
        "kind": ("Stimulyator", "Стимулятор"),
        "desc": ("Ildiz va barg o‘sishini tezlashtiradi, gullash va tugun hosil bo‘lishini yaxshilaydi.",
                 "Ускоряет рост корней и листьев, улучшает цветение и завязывание плодов."),
        "packs": ["1 L", "5 L"],
        "usages": {c: ["sekin", "gul"] for c in FIELD_CROPS},
        "texts": "fert",
    },
    {
        "slug": "npk-20-20-20", "cat": "ogit", "shape": "bag", "popular": True,
        "name": ("NPK kompleks o‘g‘it 20-20-20", "Комплексное удобрение NPK 20-20-20"),
        "kind": ("Kompleks o‘g‘it", "Комплексное удобрение"),
        "desc": ("Azot, fosfor va kaliy muvozanatli. Barglar sarg‘ayishi va sekin o‘sishda yordam beradi.",
                 "Сбалансированный азот, фосфор и калий. Помогает при пожелтении листьев и медленном росте."),
        "packs": ["1 kg", "10 kg"],
        "usages": {c: ["sargayish", "sekin"] for c in FIELD_CROPS},
        "texts": "fert",
    },
    {
        "slug": "kanaga-qarshi-akaritsid", "cat": "himoya", "shape": "bottle", "popular": False,
        "name": ("Kanaga qarshi akaritsid", "Акарицид от клещей"),
        "kind": ("Akaritsid", "Акарицид"),
        "desc": ("O‘rgimchakkanaga qarshi. Tuxum va voyaga yetgan kanalarga ta’sir qiladi.",
                 "Против паутинного клеща. Действует на яйца и взрослых особей."),
        "packs": ["250 ml", "1 L"],
        "usages": {c: ["kana"] for c in ["pomidor", "bodring", "olma", "uzum", "goza"]},
        "texts": "spray",
    },
    {
        "slug": "zamburug-fungitsid", "cat": "himoya", "shape": "bottle", "popular": False,
        "name": ("Zamburug‘ kasalliklariga qarshi fungitsid", "Фунгицид от грибковых болезней"),
        "kind": ("Fungitsid", "Фунгицид"),
        "desc": ("Un-shudring, fitoftoroz va kulrang chirishning oldini oladi va davolaydi.",
                 "Профилактика и лечение мучнистой росы, фитофтороза и серой гнили."),
        "packs": ["500 ml", "1 L"],
        "usages": {
            "pomidor": ["unshudring", "fitoftoroz"],
            "bodring": ["unshudring"],
            "olma": ["unshudring"],
            "uzum": ["unshudring", "chirish"],
            "kartoshka": ["fitoftoroz"],
        },
        "texts": "spray",
    },
    {
        "slug": "tarakanga-qarshi-gel", "cat": "uy", "shape": "tube", "popular": True,
        "name": ("Tarakanga qarshi gel", "Гель от тараканов"),
        "kind": ("Gel", "Гель"),
        "desc": ("Tarakan va chumolilarga qarshi tayyor gel. Hidsiz, uy ichida ishlatish uchun.",
                 "Готовый гель от тараканов и муравьёв. Без запаха, для использования в помещении."),
        "packs": ["30 g"],
        "usages": {"uy": ["tarakan", "chumoli"]},
        "texts": "home",
    },
]

TEXTS = {
    "spray": (SPRAY_USAGE_UZ, SPRAY_USAGE_RU, SPRAY_SAFETY_UZ, SPRAY_SAFETY_RU),
    "fert": (FERT_USAGE_UZ, FERT_USAGE_RU, FERT_SAFETY_UZ, FERT_SAFETY_RU),
    "home": (HOME_USAGE_UZ, HOME_USAGE_RU, HOME_SAFETY_UZ, HOME_SAFETY_RU),
}


def reset(db: Session) -> None:
    for model in (ProductUsage, ProductVariant, Product, CropProblem, Problem, Crop, Category):
        db.execute(delete(model))
    db.commit()


def seed(db: Session) -> None:
    cats = {}
    for i, (slug, uz, ru, s_uz, s_ru, d_uz, d_ru) in enumerate(CATEGORIES):
        cats[slug] = Category(slug=slug, name_uz=uz, name_ru=ru, short_uz=s_uz, short_ru=s_ru,
                              description_uz=d_uz, description_ru=d_ru, sort=i)
    crops = {slug: Crop(slug=slug, name_uz=uz, name_ru=ru, color=color, sort=i)
             for i, (slug, uz, ru, color) in enumerate(CROPS)}
    problems = {slug: Problem(slug=slug, name_uz=uz, name_ru=ru, type=typ, sort=i)
                for i, (slug, uz, ru, typ) in enumerate(PROBLEMS)}
    db.add_all([*cats.values(), *crops.values(), *problems.values()])
    db.flush()

    # Ekin ro'yxatidagi muammolar + mahsulot bog'langan har bir juftlik (aks holda tanlashda ko'rinmaydi)
    pairs = {(c, ps) for c, slugs in CROP_PROBLEMS.items() for ps in slugs}
    pairs |= {(c, ps) for item in PRODUCTS for c, slugs in item["usages"].items() for ps in slugs}
    for crop_slug, ps in sorted(pairs):
        db.add(CropProblem(crop_id=crops[crop_slug].id, problem_id=problems[ps].id))

    for i, item in enumerate(PRODUCTS):
        usage_uz, usage_ru, safety_uz, safety_ru = TEXTS[item["texts"]]
        product = Product(
            slug=item["slug"], category=cats[item["cat"]], pack_shape=item["shape"],
            name_uz=item["name"][0], name_ru=item["name"][1],
            kind_uz=item["kind"][0], kind_ru=item["kind"][1],
            description_uz=item["desc"][0], description_ru=item["desc"][1],
            usage_uz=usage_uz, usage_ru=usage_ru, safety_uz=safety_uz, safety_ru=safety_ru,
            waiting_days=None, is_popular=item["popular"], sort=i,
        )
        for j, pack in enumerate(item["packs"]):
            product.variants.append(ProductVariant(pack_label=pack, price=None, stock=100, sort=j))
        for crop_slug, problem_slugs in item["usages"].items():
            for ps in problem_slugs:
                product.usages.append(
                    ProductUsage(crop=crops[crop_slug], problem=problems[ps], dose_text=None)
                )
        db.add(product)
    db.commit()


def main() -> None:
    with SessionLocal() as db:
        if "--reset" in sys.argv:
            reset(db)
        elif db.scalars(select(Category).limit(1)).first():
            print("Baza allaqachon to'ldirilgan. Qayta to'ldirish uchun: --reset")
            return
        seed(db)
        print("Namunaviy ma'lumotlar qo'shildi.")


if __name__ == "__main__":
    main()
