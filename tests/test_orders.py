from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Order, OrderStatus, ProductVariant
from app.services import telegram
from app.services.orders import get_order

VALID = {
    "customer_name": "Ism Familiya",
    "phone": "90 123 45 67",
    "region": "samarqand",
    "address": "Urgut tumani, 12-uy",
    "delivery_method": "delivery",
    "consent": "1",
}


def _variant(db, pack="250 ml"):
    return db.scalars(select(ProductVariant).where(ProductVariant.pack_label == pack)).first()


def _add(client, variant_id, qty=1):
    return client.post("/savatcha/qoshish", data={"variant_id": variant_id, "qty": qty})


def test_cart_add_update_remove(client, db):
    v = _variant(db)
    _add(client, v.id, 2)
    r = client.get("/savatcha")
    assert "Mahsulotlar (2 dona)" in r.text

    client.post("/savatcha/yangilash", data={"variant_id": v.id, "qty": 5})
    assert "Mahsulotlar (5 dona)" in client.get("/savatcha").text

    client.post("/savatcha/yangilash", data={"variant_id": v.id, "qty": 0})
    assert "Savatcha bo‘sh." in client.get("/savatcha").text


def test_out_of_stock_not_added(client, db):
    v = _variant(db)
    v.stock = 0
    db.commit()
    _add(client, v.id)
    assert "Savatcha bo‘sh." in client.get("/savatcha").text


def test_order_validation_errors(client, db):
    _add(client, _variant(db).id)
    r = client.post("/buyurtma", data={**VALID, "phone": "123", "consent": ""})
    assert r.status_code == 422
    assert "Telefon raqamni to‘liq yozing" in r.text
    assert "roziligingiz kerak" in r.text
    # Kiritilgan qiymatlar saqlanadi
    assert 'value="Ism Familiya"' in r.text


def test_pickup_does_not_need_address(client, db):
    _add(client, _variant(db).id)
    r = client.post(
        "/buyurtma", data={**VALID, "delivery_method": "pickup", "address": ""}, follow_redirects=False
    )
    assert r.status_code == 303


def test_empty_cart_order_rejected(client, db):
    r = client.post("/buyurtma", data=VALID)
    assert r.status_code == 422
    assert db.scalars(select(Order)).first() is None


def test_order_flow(client, db):
    v = _variant(db)
    v.price = 45000
    db.commit()
    _add(client, v.id, 2)

    r = client.post("/buyurtma", data=VALID, follow_redirects=False)
    assert r.status_code == 303
    done = client.get(r.headers["location"])
    assert "Buyurtmangiz qabul qilindi" in done.text
    assert "#0001" in done.text
    assert "90\u00a0000 so‘m" in done.text  # minglar bo‘linmas probel bilan

    order = db.scalars(select(Order)).one()
    assert order.phone == "+998 90 123 45 67"
    assert order.total == 90000
    assert order.status == OrderStatus.new
    assert order.consent_at is not None
    # Savatcha tozalandi
    assert "Savatcha bo‘sh." in client.get("/savatcha").text


def test_done_page_only_for_owner(client, db):
    _add(client, _variant(db).id)
    location = client.post("/buyurtma", data=VALID, follow_redirects=False).headers["location"]
    assert TestClient(app).get(location).status_code == 404


def test_telegram_message_and_buttons(client, db):
    _add(client, _variant(db).id)
    client.post("/buyurtma", data={**VALID, "customer_name": "<b>Ali</b>"})
    order = get_order(db, 1)
    text = telegram.order_text(order)
    assert "Yangi buyurtma #0001" in text
    assert "&lt;b&gt;Ali&lt;/b&gt;" in text  # HTML escape
    assert "Shiraga qarshi insektitsid, 250 ml × 1" in text
    buttons = [b["text"] for row in telegram.order_keyboard(order)["inline_keyboard"] for b in row]
    assert buttons == ["Qabul qilish", "Qo‘ng‘iroq qildim", "Bekor qilish"]


def test_webhook_requires_secret(client):
    assert client.post("/telegram/webhook", json={}).status_code == 403
    r = client.post(
        "/telegram/webhook", json={}, headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}
    )
    assert r.status_code == 403


def test_webhook_updates_status(client, db, monkeypatch):
    calls = []
    monkeypatch.setattr(telegram, "_api", lambda method, payload: calls.append((method, payload)))
    _add(client, _variant(db).id)
    client.post("/buyurtma", data=VALID)

    def press(chat_id, data):
        return client.post(
            "/telegram/webhook",
            json={
                "callback_query": {
                    "id": "q1",
                    "data": data,
                    "message": {"message_id": 10, "chat": {"id": chat_id}},
                }
            },
            headers={"X-Telegram-Bot-Api-Secret-Token": "hook-secret"},
        )

    # Boshqa chatdan bosilsa — o'zgarmaydi
    press(123, "st:1:cancelled")
    db.expire_all()
    assert db.get(Order, 1).status == OrderStatus.new

    press(777, "st:1:accepted")
    db.expire_all()
    assert db.get(Order, 1).status == OrderStatus.accepted
    edit = next(p for m, p in calls if m == "editMessageText")
    assert "Holati: <b>Qabul qilindi</b>" in edit["text"]
    assert edit["message_id"] == 10

    press(777, "st:1:bogus")
    db.expire_all()
    assert db.get(Order, 1).status == OrderStatus.accepted
