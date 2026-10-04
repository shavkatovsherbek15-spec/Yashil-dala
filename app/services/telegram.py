"""Do'kon egasining Telegram chatiga buyurtma xabari va holat tugmalari."""

import html
import logging

import httpx

from app.config import get_settings
from app.db import SessionLocal
from app.models import DeliveryMethod, Order, OrderStatus
from app.regions import region_name
from app.services.orders import get_order

log = logging.getLogger(__name__)

STATUS_LABELS = {
    OrderStatus.new: "Yangi",
    OrderStatus.accepted: "Qabul qilindi",
    OrderStatus.called: "Qo‘ng‘iroq qilindi",
    OrderStatus.delivered: "Yetkazildi",
    OrderStatus.cancelled: "Bekor qilindi",
}

# Tugma: (matn, yangi holat)
BUTTONS = {
    OrderStatus.new: [("Qabul qilish", OrderStatus.accepted), ("Qo‘ng‘iroq qildim", OrderStatus.called)],
    OrderStatus.accepted: [("Qo‘ng‘iroq qildim", OrderStatus.called), ("Yetkazildi", OrderStatus.delivered)],
    OrderStatus.called: [("Yetkazildi", OrderStatus.delivered)],
}


def _money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " so‘m" if value else "[narx] so‘m"


def order_text(order: Order) -> str:
    e = html.escape
    method = "yetkazib berish" if order.delivery_method == DeliveryMethod.delivery else "o‘zi olib ketadi"
    lines = [
        f"<b>Yangi buyurtma #{order.number}</b>",
        f"Mijoz: {e(order.customer_name)}",
        f"Telefon: {e(order.phone)}",
        f"Viloyat: {e(region_name(order.region, 'uz'))}",
    ]
    if order.address:
        lines.append(f"Manzil: {e(order.address)}")
    lines += [f"Olish: {method}", "", "<b>Mahsulotlar:</b>"]
    for i, item in enumerate(order.items, 1):
        lines.append(f"{i}. {e(item.variant.product.name_uz)}, {e(item.variant.pack_label)} × {item.qty}")
    lines += [
        "",
        f"<b>Jami: {_money(order.total)}</b>",
        "To‘lov: qabul qilganda",
        f"Izoh: {e(order.comment) or '—'}",
        "",
        f"Holati: <b>{STATUS_LABELS[order.status]}</b>",
    ]
    return "\n".join(lines)


def order_keyboard(order: Order) -> dict:
    row = [
        {"text": text, "callback_data": f"st:{order.id}:{status.value}"}
        for text, status in BUTTONS.get(order.status, [])
    ]
    rows = [row] if row else []
    if order.status not in (OrderStatus.delivered, OrderStatus.cancelled):
        rows.append([{"text": "Bekor qilish", "callback_data": f"st:{order.id}:cancelled"}])
    return {"inline_keyboard": rows}


def _api(method: str, payload: dict) -> dict | None:
    token = get_settings().telegram_bot_token
    if not token:
        log.info("Telegram token yo'q, %s o'tkazib yuborildi: %s", method, payload.get("text", "")[:80])
        return None
    try:
        r = httpx.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json().get("result")
    except httpx.HTTPError:
        log.exception("Telegram %s xatosi", method)
        return None


def notify_new_order(order_id: int) -> None:
    """BackgroundTasks orqali chaqiriladi — o'z sessiyasini ochadi."""
    settings = get_settings()
    if not settings.telegram_chat_id:
        log.info("TELEGRAM_CHAT_ID yo'q, buyurtma #%s xabari yuborilmadi", order_id)
        return
    with SessionLocal() as db:
        order = get_order(db, order_id)
        if order is None:
            return
        result = _api(
            "sendMessage",
            {
                "chat_id": settings.telegram_chat_id,
                "text": order_text(order),
                "parse_mode": "HTML",
                "reply_markup": order_keyboard(order),
            },
        )
        if result:
            order.telegram_message_id = result["message_id"]
            db.commit()


def handle_update(update: dict) -> None:
    """Inline tugma bosilganda: holatni yangilash va xabarni tahrirlash."""
    query = update.get("callback_query")
    if not query:
        return
    settings = get_settings()
    chat_id = str(query.get("message", {}).get("chat", {}).get("id", ""))
    if chat_id != str(settings.telegram_chat_id):
        _api("answerCallbackQuery", {"callback_query_id": query["id"], "text": "Ruxsat yo‘q"})
        return

    try:
        prefix, order_id, status = query.get("data", "").split(":")
        if prefix != "st":
            raise ValueError
        new_status = OrderStatus(status)
        order_id_int = int(order_id)
    except ValueError:
        _api("answerCallbackQuery", {"callback_query_id": query["id"]})
        return

    with SessionLocal() as db:
        order = get_order(db, order_id_int)
        if order is None:
            _api("answerCallbackQuery", {"callback_query_id": query["id"], "text": "Buyurtma topilmadi"})
            return
        order.status = new_status
        db.commit()
        _api(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": query["message"]["message_id"],
                "text": order_text(order),
                "parse_mode": "HTML",
                "reply_markup": order_keyboard(order),
            },
        )
        _api(
            "answerCallbackQuery",
            {"callback_query_id": query["id"], "text": STATUS_LABELS[new_status]},
        )


def refresh_order_message(order_id: int) -> None:
    """Admin paneldan holat o'zgarganda bot xabarini ham yangilash."""
    chat_id = get_settings().telegram_chat_id
    if not chat_id:
        return
    with SessionLocal() as db:
        order = get_order(db, order_id)
        if order is None or not order.telegram_message_id:
            return
        _api(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": order.telegram_message_id,
                "text": order_text(order),
                "parse_mode": "HTML",
                "reply_markup": order_keyboard(order),
            },
        )
