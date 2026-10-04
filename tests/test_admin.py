import html
import re

import pytest
from sqlalchemy import select

from app.admin import auth
from app.models import (
    AdminUser,
    Crop,
    CropProblem,
    Order,
    OrderStatus,
    Problem,
    Product,
    ProductImage,
    ProductUsage,
    ProductVariant,
)

PASSWORD = "test-parol-123"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def _reset_throttle():
    auth._fails.clear()


@pytest.fixture
def admin_user(db):
    user = AdminUser(username="admin", password_hash=auth.hash_password(PASSWORD))
    db.add(user)
    db.commit()
    return user


def csrf_of(client, url="/admin/kirish"):
    html = client.get(url).text
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


@pytest.fixture
def admin(client, admin_user):
    token = csrf_of(client)
    r = client.post("/admin/kirish", data={"csrf": token, "username": "admin", "password": PASSWORD},
                    follow_redirects=False)
    assert r.status_code == 303
    client.csrf = csrf_of(client, "/admin")  # kirgandan keyin token yangilanadi
    return client


def _get(db, model, slug):
    return db.scalars(select(model).where(model.slug == slug)).one()


# ---------- Kirish va himoya ----------

def test_password_hash():
    h = auth.hash_password("salom-dunyo-1")
    assert auth.verify_password("salom-dunyo-1", h)
    assert not auth.verify_password("boshqa", h)
    assert not auth.verify_password("x", "buzilgan")


def test_admin_requires_login(client):
    r = client.get("/admin/mahsulotlar?q=x", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/kirish?next=/admin/mahsulotlar%3Fq%3Dx"


def test_wrong_password_and_throttle(client, admin_user):
    token = csrf_of(client)
    for _ in range(5):
        r = client.post("/admin/kirish", data={"csrf": token, "username": "admin", "password": "xato"})
        assert r.status_code == 401
    r = client.post("/admin/kirish", data={"csrf": token, "username": "admin", "password": PASSWORD})
    assert r.status_code == 429


def test_login_requires_csrf(client, admin_user):
    client.get("/admin/kirish")
    r = client.post("/admin/kirish", data={"csrf": "soxta", "username": "admin", "password": PASSWORD})
    assert r.status_code == 400


def test_post_without_csrf_rejected(admin):
    r = admin.post("/admin/narxlar", data={"p-1": "100", "s-1": "1"})
    assert r.status_code == 400


def test_logout(admin):
    admin.post("/admin/chiqish", data={"csrf": admin.csrf})
    assert admin.get("/admin", follow_redirects=False).status_code == 303


def test_inactive_admin_kicked_out(admin, db, admin_user):
    admin_user.is_active = False
    db.commit()
    assert admin.get("/admin", follow_redirects=False).status_code == 303


# ---------- Sahifalar ----------

@pytest.mark.parametrize("url", [
    "/admin", "/admin/buyurtmalar", "/admin/mahsulotlar", "/admin/mahsulotlar/yangi",
    "/admin/mahsulotlar/1", "/admin/narxlar", "/admin/malumotnoma", "/admin/ekinlar/1",
    "/admin/ekinlar/yangi", "/admin/muammolar/1", "/admin/muammolar/yangi",
])
def test_admin_pages_ok(admin, url):
    assert admin.get(url).status_code == 200


# ---------- Buyurtmalar ----------

def _place_order(client, db):
    v = db.scalars(select(ProductVariant)).first()
    client.post("/savatcha/qoshish", data={"variant_id": v.id})
    client.post("/buyurtma", data={
        "customer_name": "Ali Valiyev", "phone": "901234567", "region": "samarqand",
        "address": "Urgut, 12-uy", "delivery_method": "delivery", "consent": "1",
    })
    return db.scalars(select(Order)).one()


def test_order_list_search_and_status(admin, db, monkeypatch):
    calls = []
    monkeypatch.setattr("app.admin.routes.refresh_order_message", lambda oid: calls.append(oid))
    order = _place_order(admin, db)

    assert "Ali Valiyev" in admin.get("/admin/buyurtmalar?q=1234567").text
    assert "Ali Valiyev" not in admin.get("/admin/buyurtmalar?q=999999").text
    assert "Ali Valiyev" not in admin.get("/admin/buyurtmalar?status=delivered").text

    admin.post(f"/admin/buyurtmalar/{order.id}/holat", data={"csrf": admin.csrf, "status": "called"})
    db.expire_all()
    assert db.get(Order, order.id).status == OrderStatus.called
    assert calls == [order.id]


# ---------- Mahsulot formasi ----------

def _form_from_page(client, url):
    """Sahifadagi formani brauzer kabi yig'ib olish (input/select/textarea)."""
    page_html = client.get(url).text
    form_html = page_html[page_html.index('<form method="post" action="/admin/mahsulotlar'):]
    form_html = form_html[: form_html.index("</form>")]
    data = {}
    for m in re.finditer(r'<input([^>]*)>', form_html):
        attrs = m.group(1)
        name = re.search(r'name="([^"]+)"', attrs)
        if not name:
            continue
        if 'type="checkbox"' in attrs:
            if " checked" in attrs:
                data[name.group(1)] = "1"
            continue
        value = re.search(r'value="([^"]*)"', attrs)
        data[name.group(1)] = html.unescape(value.group(1)) if value else ""
    for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', form_html, re.DOTALL):
        sel = re.search(r'<option value="([^"]*)" selected', m.group(2))
        data[m.group(1)] = sel.group(1) if sel else ""
    for m in re.finditer(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', form_html, re.DOTALL):
        data[m.group(1)] = html.unescape(m.group(2))
    return data


def test_create_product(admin, db):
    crop = _get(db, Crop, "piyoz")
    problem = _get(db, Problem, "trips")
    data = _form_from_page(admin, "/admin/mahsulotlar/yangi")
    data.update({
        "name_uz": "Yangi o‘g‘it", "category_id": "1", "registration_no": "UZ-123",
        "v-0-pack": "1 kg", "v-0-price": "25 000", "v-0-stock": "10",
        "u-0-crop": str(crop.id), "u-0-problem": str(problem.id), "u-0-dose": "2 kg/ga",
    })
    r = admin.post("/admin/mahsulotlar/yangi", data=data, follow_redirects=False)
    assert r.status_code == 303

    product = _get(db, Product, "yangi-ogit")
    assert product.name_ru == "Yangi o‘g‘it"  # RU bo'sh — UZ olindi
    assert [(v.pack_label, v.price, v.stock) for v in product.variants] == [("1 kg", 25000, 10)]
    # Muammo piyoz ro'yxatida yo'q edi — avtomatik bog'landi va tanlashda chiqadi
    assert db.get(CropProblem, (crop.id, problem.id)) is not None
    assert "Yangi o‘g‘it" in admin.get("/tanlash?crop=piyoz&problem=trips").text


def test_product_validation(admin, db):
    data = _form_from_page(admin, "/admin/mahsulotlar/yangi")
    data.update({"name_uz": "", "category_id": "", "waiting_days": "-3"})
    r = admin.post("/admin/mahsulotlar/yangi", data=data)
    assert r.status_code == 422
    for msg in ("Nomi (UZ) majburiy", "Kategoriyani tanlang", "Kutish muddati", "Kamida bitta qadoq"):
        assert msg in r.text


def test_duplicate_usage_rejected(admin, db):
    p = _get(db, Product, "shiraga-qarshi-insektitsid")
    data = _form_from_page(admin, f"/admin/mahsulotlar/{p.id}")
    first = next(k for k in data if re.fullmatch(r"u-\d+-id", k) and data[k])
    i = first.split("-")[1]
    blank = next(k.split("-")[1] for k in data if re.fullmatch(r"u-\d+-id", k) and not data[k])
    data[f"u-{blank}-crop"] = data[f"u-{i}-crop"]
    data[f"u-{blank}-problem"] = data[f"u-{i}-problem"]
    r = admin.post(f"/admin/mahsulotlar/{p.id}", data=data)
    assert r.status_code == 422
    assert "takrorlangan" in r.text


def test_edit_product_variants_and_usages(admin, db):
    p = _get(db, Product, "shiraga-qarshi-insektitsid")
    data = _form_from_page(admin, f"/admin/mahsulotlar/{p.id}")
    # 250 ml narxi, 5 L ni o'chirish, yangi 10 L
    labels = {data[k]: k.split("-")[1] for k in data if re.fullmatch(r"v-\d+-pack", k)}
    data[f"v-{labels['250 ml']}-price"] = "45000"
    data[f"v-{labels['5 L']}-delete"] = "1"
    blank = next(k.split("-")[1] for k in data if re.fullmatch(r"v-\d+-id", k) and not data[k])
    data.update({f"v-{blank}-pack": "10 L", f"v-{blank}-price": "300000", f"v-{blank}-stock": "3"})
    # Olma qo'llanishini o'chirish
    olma = str(_get(db, Crop, "olma").id)
    u = next(k.split("-")[1] for k in data if re.fullmatch(r"u-\d+-crop", k) and data[k] == olma)
    data[f"u-{u}-delete"] = "1"
    data["csrf"] = admin.csrf

    r = admin.post(f"/admin/mahsulotlar/{p.id}", data=data, follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    p = db.get(Product, p.id)
    assert {v.pack_label: v.price for v in p.variants} == {"250 ml": 45000, "1 L": None, "10 L": 300000}
    assert "olma" not in {u.crop.slug for u in p.usages}
    assert "Olma · Shira — 0 ta topildi" in admin.get("/tanlash?crop=olma&problem=shira").text


def test_variant_in_order_cannot_be_deleted(admin, db):
    order = _place_order(admin, db)
    variant = order.items[0].variant
    data = _form_from_page(admin, f"/admin/mahsulotlar/{variant.product_id}")
    i = next(k.split("-")[1] for k in data if re.fullmatch(r"v-\d+-id", k) and data[k] == str(variant.id))
    data[f"v-{i}-delete"] = "1"
    r = admin.post(f"/admin/mahsulotlar/{variant.product_id}", data=data)
    assert r.status_code == 422
    assert "buyurtmalarda bor" in r.text
    db.expire_all()
    assert db.get(ProductVariant, variant.id) is not None


def test_image_upload_and_delete(admin, db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.admin.media.media_root", lambda: tmp_path)
    p = _get(db, Product, "npk-20-20-20")
    r = admin.post(f"/admin/mahsulotlar/{p.id}/rasm", data={"csrf": admin.csrf},
                   files={"image": ("a.png", PNG, "image/png")})
    assert r.status_code == 200
    image = db.scalars(select(ProductImage).where(ProductImage.product_id == p.id)).one()
    assert (tmp_path / image.url.removeprefix("/media/")).exists()
    assert image.url in admin.get("/mahsulot/npk-20-20-20").text

    # Rasm emas — rad etiladi
    admin.post(f"/admin/mahsulotlar/{p.id}/rasm", data={"csrf": admin.csrf},
               files={"image": ("x.png", b"<?php echo 1;", "image/png")})
    assert len(db.scalars(select(ProductImage)).all()) == 1

    admin.post(f"/admin/mahsulotlar/{p.id}/rasm/{image.id}", data={"csrf": admin.csrf, "action": "delete"})
    db.expire_all()
    assert db.scalars(select(ProductImage)).first() is None
    assert not list(tmp_path.iterdir())


# ---------- Narx va qoldiq ----------

def test_bulk_prices(admin, db):
    v1, v2 = db.scalars(select(ProductVariant).order_by(ProductVariant.id).limit(2)).all()
    admin.post("/admin/narxlar", data={
        "csrf": admin.csrf, f"p-{v1.id}": "12 500", f"s-{v1.id}": "7", f"p-{v2.id}": "", f"s-{v2.id}": "0",
    })
    db.expire_all()
    assert (db.get(ProductVariant, v1.id).price, db.get(ProductVariant, v1.id).stock) == (12500, 7)
    assert db.get(ProductVariant, v2.id).stock == 0

    r = admin.post("/admin/narxlar", data={"csrf": admin.csrf, f"p-{v1.id}": "abc", f"s-{v1.id}": "1"})
    assert "Xato qiymat" in r.text
    db.expire_all()
    assert db.get(ProductVariant, v1.id).price == 12500


# ---------- Ma'lumotnoma ----------

def test_crop_problems_edit(admin, db):
    piyoz = _get(db, Crop, "piyoz")
    sekin = _get(db, Problem, "sekin")
    trips = _get(db, Problem, "trips")
    # "sekin" ga mahsulot bog'langan — olib tashlansa ham qoladi; "trips" qo'shiladi
    admin.post(f"/admin/ekinlar/{piyoz.id}", data={
        "csrf": admin.csrf, "name_uz": "Piyoz", "name_ru": "Лук", "slug": "piyoz",
        "color": "#E9A65A", "sort": "6", "problems": [str(trips.id)],
    })
    db.expire_all()
    linked = {p.slug for p in db.get(Crop, piyoz.id).problems}
    # sekin, sargayish, gul — mahsulotlar bog'langan, shuning uchun olib tashlanmaydi
    assert linked == {"trips", sekin.slug, "sargayish", "gul"}


def test_new_problem_and_delete_guard(admin, db):
    admin.post("/admin/muammolar/yangi", data={
        "csrf": admin.csrf, "name_uz": "Nematoda", "name_ru": "Нематода", "type": "pest", "sort": "20",
    })
    nem = _get(db, Problem, "nematoda")
    assert nem.type.value == "pest"

    shira = _get(db, Problem, "shira")
    admin.post(f"/admin/muammolar/{shira.id}", data={"csrf": admin.csrf, "action": "delete"})
    db.expire_all()
    assert db.get(Problem, shira.id) is not None  # mahsulot bog'langan

    admin.post(f"/admin/muammolar/{nem.id}", data={"csrf": admin.csrf, "action": "delete"})
    db.expunge_all()
    assert db.scalar(select(Problem).where(Problem.slug == "nematoda")) is None


def test_usage_count_unchanged_by_category_save(admin, db):
    before = len(db.scalars(select(ProductUsage)).all())
    admin.post("/admin/kategoriya/1", data={
        "csrf": admin.csrf, "name_uz": "O‘g‘itlar", "name_ru": "Удобрения", "short_uz": "O‘g‘it",
        "short_ru": "Удобр.", "description_uz": "", "description_ru": "",
    })
    assert len(db.scalars(select(ProductUsage)).all()) == before
    assert "Удобр." in admin.get("/admin/malumotnoma").text
