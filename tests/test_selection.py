from sqlalchemy import select

from app.models import Crop, Problem, Product
from app.services.catalog import find_for_problem


def _get(db, model, slug):
    return db.scalars(select(model).where(model.slug == slug)).one()


def _names(db, crop, problem):
    rows = find_for_problem(db, _get(db, Crop, crop), _get(db, Problem, problem))
    return sorted(p.slug for p, _ in rows)


def test_only_products_registered_for_crop(db):
    assert _names(db, "pomidor", "shira") == ["shiraga-qarshi-insektitsid"]
    assert _names(db, "olma", "kana") == ["kanaga-qarshi-akaritsid"]
    assert _names(db, "kartoshka", "fitoftoroz") == ["zamburug-fungitsid"]
    # Insektitsid trips uchun faqat pomidor/bodringda ro'yxatdan o'tgan
    assert _names(db, "olma", "trips") == []


def test_no_product_for_problem(db):
    assert _names(db, "kartoshka", "kolorado") == []


def test_inactive_product_hidden(db):
    p = _get(db, Product, "shiraga-qarshi-insektitsid")
    p.is_active = False
    db.commit()
    assert _names(db, "pomidor", "shira") == []


def test_select_page_states(client):
    r = client.get("/tanlash")
    assert "Avval yuqoridan ekinni tanlang." in r.text

    r = client.get("/tanlash?crop=pomidor&problem=shira")
    assert "Pomidor · Shira — 1 ta topildi" in r.text
    assert "/mahsulot/shiraga-qarshi-insektitsid" in r.text

    r = client.get("/tanlash?crop=kartoshka&problem=kolorado")
    assert "hozircha vositamiz yo‘q" in r.text


def test_problem_not_listed_for_crop_is_ignored(client):
    # Piyoz uchun "shira" muammosi ro'yxatda yo'q — natija ko'rsatilmaydi
    r = client.get("/tanlash?crop=piyoz&problem=shira")
    assert "ta topildi" not in r.text
    assert "Ekin va muammoni tanlang" in r.text


def test_russian(client):
    client.cookies.set("lang", "ru")
    r = client.get("/tanlash?crop=uy&problem=tarakan")
    assert "Подбор по проблеме" in r.text
    assert "Дом · Тараканы — найдено: 1" in r.text
