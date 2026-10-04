import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import DeliveryMethod, Order, OrderItem, Product, ProductVariant
from app.regions import is_region
from app.services.cart import Cart


@dataclass
class OrderForm:
    customer_name: str = ""
    phone: str = ""  # +998 dan keyingi 9 ta raqam
    region: str = ""
    address: str = ""
    delivery_method: str = DeliveryMethod.delivery.value
    comment: str = ""
    consent: bool = False
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def phone_digits(self) -> str:
        digits = re.sub(r"\D", "", self.phone)
        if len(digits) == 12 and digits.startswith("998"):
            digits = digits[3:]
        return digits

    def validate(self) -> bool:
        self.errors = {}
        if len(self.customer_name.strip()) < 2:
            self.errors["customer_name"] = "err_name"
        if len(self.phone_digits) != 9:
            self.errors["phone"] = "err_phone"
        if not is_region(self.region):
            self.errors["region"] = "err_region"
        if self.delivery_method not in DeliveryMethod.__members__:
            self.delivery_method = DeliveryMethod.delivery.value
        if self.delivery_method == DeliveryMethod.delivery and len(self.address.strip()) < 5:
            self.errors["address"] = "err_address"
        if not self.consent:
            self.errors["consent"] = "err_consent"
        return not self.errors


def format_phone(digits: str) -> str:
    d = digits
    return f"+998 {d[0:2]} {d[2:5]} {d[5:7]} {d[7:9]}"


def create_order(db: Session, form: OrderForm, cart: Cart, *, delivery_price: int, lang: str) -> Order:
    is_delivery = form.delivery_method == DeliveryMethod.delivery
    delivery_cost = delivery_price if is_delivery else 0
    order = Order(
        customer_name=form.customer_name.strip()[:200],
        phone=format_phone(form.phone_digits),
        region=form.region,
        address=form.address.strip(),
        delivery_method=DeliveryMethod(form.delivery_method),
        comment=form.comment.strip(),
        delivery_price=delivery_cost,
        lang=lang,
        consent_at=datetime.now(UTC),
    )
    total = delivery_cost
    for line in cart.lines:
        unit = line.variant.price or 0
        order.items.append(OrderItem(variant_id=line.variant.id, qty=line.qty, unit_price=unit))
        total += unit * line.qty
    order.total = total
    db.add(order)
    db.flush()
    order.number = f"{order.id:04d}"
    db.commit()
    return order


def get_order(db: Session, order_id: int) -> Order | None:
    q = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.items)
            .selectinload(OrderItem.variant)
            .selectinload(ProductVariant.product)
            .selectinload(Product.category)
        )
    )
    return db.scalars(q).first()
