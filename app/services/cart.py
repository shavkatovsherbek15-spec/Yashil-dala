"""Savatcha sessiya cookie'sida saqlanadi: {"<variant_id>": qty}."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from starlette.requests import Request

from app.models import Product, ProductVariant

MAX_QTY = 99


@dataclass
class CartLine:
    variant: ProductVariant
    qty: int

    @property
    def product(self) -> Product:
        return self.variant.product

    @property
    def subtotal(self) -> int | None:
        return None if self.variant.price is None else self.variant.price * self.qty


@dataclass
class Cart:
    lines: list[CartLine]

    @property
    def count(self) -> int:
        return sum(line.qty for line in self.lines)

    @property
    def items_total(self) -> int | None:
        subtotals = [line.subtotal for line in self.lines]
        return None if None in subtotals else sum(subtotals)  # type: ignore[arg-type]


def raw(request: Request) -> dict[str, int]:
    return dict(request.session.get("cart", {}))


def _save(request: Request, data: dict[str, int]) -> None:
    request.session["cart"] = {k: v for k, v in data.items() if v > 0}


def count(request: Request) -> int:
    return sum(raw(request).values())


def add(request: Request, variant_id: int, qty: int = 1) -> None:
    data = raw(request)
    key = str(variant_id)
    data[key] = min(MAX_QTY, data.get(key, 0) + max(1, qty))
    _save(request, data)


def set_qty(request: Request, variant_id: int, qty: int) -> None:
    data = raw(request)
    data[str(variant_id)] = max(0, min(MAX_QTY, qty))
    _save(request, data)


def clear(request: Request) -> None:
    request.session.pop("cart", None)


def load(request: Request, db: Session) -> Cart:
    data = raw(request)
    if not data:
        return Cart(lines=[])
    ids = [int(k) for k in data]
    variants = db.scalars(
        select(ProductVariant)
        .where(ProductVariant.id.in_(ids))
        .options(
            selectinload(ProductVariant.product).selectinload(Product.category),
        )
    ).all()
    by_id = {v.id: v for v in variants if v.product.is_active}
    # Bazadan o'chirilgan variantlarni savatdan ham olib tashlaymiz
    if len(by_id) != len(data):
        _save(request, {k: v for k, v in data.items() if int(k) in by_id})
    return Cart(lines=[CartLine(by_id[i], data[str(i)]) for i in ids if i in by_id])
