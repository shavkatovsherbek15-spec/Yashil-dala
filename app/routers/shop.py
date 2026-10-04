from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ProductVariant
from app.regions import REGIONS
from app.services import cart as cart_service
from app.services import orders
from app.services.telegram import notify_new_order
from app.web import get_lang, render, safe_next

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]


def _cart_page(request: Request, db: Session, form: orders.OrderForm, status_code: int = 200):
    settings = get_settings()
    cart = cart_service.load(request, db)
    items_total = cart.items_total
    delivery = settings.delivery_price if form.delivery_method == "delivery" else 0
    return render(
        request,
        "cart.html",
        {
            "cart": cart,
            "form": form,
            "regions": REGIONS,
            "items_total": items_total,
            "delivery_price": settings.delivery_price,
            "grand_total": None if items_total is None else items_total + delivery,
        },
        status_code=status_code,
    )


@router.get("/savatcha")
def cart_page(request: Request, db: DB):
    return _cart_page(request, db, orders.OrderForm())


@router.post("/savatcha/qoshish")
def cart_add(
    request: Request,
    db: DB,
    variant_id: Annotated[int, Form()],
    qty: Annotated[int, Form()] = 1,
    next: Annotated[str, Form()] = "/savatcha",
):
    variant = db.get(ProductVariant, variant_id)
    if variant is None or not variant.product.is_active:
        raise HTTPException(404)
    if variant.stock > 0:
        cart_service.add(request, variant.id, qty)
    return RedirectResponse(safe_next(next, "/savatcha"), status_code=303)


@router.post("/savatcha/yangilash")
def cart_update(
    request: Request,
    variant_id: Annotated[int, Form()],
    qty: Annotated[int, Form()],
):
    cart_service.set_qty(request, variant_id, qty)
    return RedirectResponse("/savatcha", status_code=303)


@router.post("/buyurtma")
def place_order(
    request: Request,
    db: DB,
    background: BackgroundTasks,
    customer_name: Annotated[str, Form()] = "",
    phone: Annotated[str, Form()] = "",
    region: Annotated[str, Form()] = "",
    address: Annotated[str, Form()] = "",
    delivery_method: Annotated[str, Form()] = "delivery",
    comment: Annotated[str, Form()] = "",
    consent: Annotated[str, Form()] = "",
):
    form = orders.OrderForm(
        customer_name=customer_name,
        phone=phone,
        region=region,
        address=address,
        delivery_method=delivery_method,
        comment=comment[:1000],
        consent=bool(consent),
    )
    cart = cart_service.load(request, db)
    valid = form.validate()
    if not cart.lines:
        form.errors["cart"] = "err_cart"
    if not valid or form.errors:
        return _cart_page(request, db, form, status_code=422)

    order = orders.create_order(
        db, form, cart, delivery_price=get_settings().delivery_price, lang=get_lang(request)
    )
    cart_service.clear(request)
    request.session["last_order_id"] = order.id
    background.add_task(notify_new_order, order.id)
    return RedirectResponse(f"/buyurtma/{order.id}", status_code=303)


@router.get("/buyurtma/{order_id}")
def order_done(request: Request, db: DB, order_id: int):
    # Buyurtma sahifasini faqat uni bergan brauzer ko'radi
    if request.session.get("last_order_id") != order_id:
        raise HTTPException(404)
    order = orders.get_order(db, order_id)
    if order is None:
        raise HTTPException(404)
    return render(request, "done.html", {"order": order})
