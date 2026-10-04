from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload
from starlette.datastructures import UploadFile

from app.admin import auth, media
from app.admin.auth import Admin, checked_form
from app.admin.products import PACK_SHAPES, ProductForm, slugify
from app.config import get_settings
from app.db import get_db
from app.models import (
    AdminUser,
    Category,
    Crop,
    CropProblem,
    Order,
    OrderStatus,
    Problem,
    ProblemType,
    Product,
    ProductImage,
    ProductUsage,
    ProductVariant,
)
from app.regions import region_name
from app.services.orders import get_order
from app.services.telegram import STATUS_LABELS, refresh_order_message
from app.web import render, safe_next

router = APIRouter(prefix="/admin")
DB = Annotated[Session, Depends(get_db)]

PER_PAGE = 30
LOW_STOCK = 5
PROBLEM_TYPES = {
    ProblemType.pest: "Zararkunanda",
    ProblemType.disease: "Kasallik",
    ProblemType.nutrition: "Oziqlanish",
    ProblemType.household: "Uy hasharoti",
}
_DUMMY_HASH = auth.hash_password("dummy-password-for-timing")
SHAPE_LABELS = {"bottle": "Shisha / flakon", "bag": "Qop / paket", "tube": "Tuba / shprits"}


def flash(request: Request, text: str, kind: str = "ok") -> None:
    request.session["flash"] = [kind, text]


def page(request: Request, name: str, admin: AdminUser | None, status_code: int = 200, **ctx):
    return render(
        request,
        f"admin/{name}",
        {
            "admin": admin,
            "csrf": auth.csrf_token(request),
            "flash": request.session.pop("flash", None),
            "status_labels": STATUS_LABELS,
            "region_name": region_name,
            **ctx,
        },
        status_code=status_code,
    )


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


# ---------------- Kirish ----------------

@router.get("/kirish")
def login_page(request: Request, next: str = "/admin"):
    return page(request, "login.html", None, next=safe_next(next, "/admin"))


@router.post("/kirish")
async def login_submit(request: Request, db: DB):
    form = await checked_form(request)
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    next_url = safe_next(str(form.get("next", "/admin")), "/admin")

    if auth.too_many_attempts(request):
        return page(request, "login.html", None, status_code=429, next=next_url,
                    error="Juda ko‘p urinish. 15 daqiqadan keyin qayta urinib ko‘ring.")
    user = db.scalars(select(AdminUser).where(AdminUser.username == username)).first()
    # Foydalanuvchi bo'lmasa ham xesh hisoblanadi — javob vaqti bir xil bo'lsin
    valid = auth.verify_password(password, user.password_hash if user else _DUMMY_HASH)
    if not user or not user.is_active or not valid:
        auth.record_failure(request)
        return page(request, "login.html", None, status_code=401, next=next_url,
                    username=username, error="Login yoki parol noto‘g‘ri.")
    auth.reset_failures(request)
    auth.login(request, db, user)
    return redirect(next_url)



@router.post("/chiqish")
async def logout(request: Request):
    await checked_form(request)
    auth.logout(request)
    return redirect("/admin/kirish")


# ---------------- Bosh sahifa ----------------

@router.get("")
def dashboard(request: Request, db: DB, admin: Admin):
    since = datetime.now(UTC) - timedelta(days=1)
    new_orders = list(db.scalars(
        select(Order).where(Order.status == OrderStatus.new).order_by(Order.id.desc()).limit(10)
    ))
    low_stock = list(db.scalars(
        select(ProductVariant)
        .join(Product)
        .where(Product.is_active.is_(True), ProductVariant.stock <= LOW_STOCK)
        .options(selectinload(ProductVariant.product))
        .order_by(ProductVariant.stock, Product.sort)
    ))
    stats = {
        "new": db.scalar(select(func.count()).where(Order.status == OrderStatus.new)),
        "today": db.scalar(select(func.count()).where(Order.created_at >= since)),
        "products": db.scalar(select(func.count()).select_from(Product).where(Product.is_active.is_(True))),
        "no_price": db.scalar(
            select(func.count()).select_from(ProductVariant).where(ProductVariant.price.is_(None))
        ),
    }
    return page(request, "dashboard.html", admin, new_orders=new_orders, low_stock=low_stock,
                stats=stats, low_limit=LOW_STOCK)


# ---------------- Buyurtmalar ----------------

@router.get("/buyurtmalar")
def orders_list(request: Request, db: DB, admin: Admin, status: str = "", q: str = "", p: int = 1):
    query = select(Order)
    if status in OrderStatus.__members__:
        query = query.where(Order.status == OrderStatus(status))
    q = q.strip()[:50]
    if q:
        digits = "".join(ch for ch in q if ch.isdigit())
        conds = [Order.customer_name.ilike(f"%{q}%")]
        if digits:
            conds += [Order.number.like(f"%{digits}%"),
                      func.replace(Order.phone, " ", "").like(f"%{digits}%")]
        query = query.where(or_(*conds))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    p = max(1, p)
    orders = list(db.scalars(
        query.options(selectinload(Order.items))
        .order_by(Order.id.desc()).offset((p - 1) * PER_PAGE).limit(PER_PAGE)
    ))
    counts = dict(db.execute(select(Order.status, func.count()).group_by(Order.status)).all())
    return page(request, "orders.html", admin, orders=orders, status=status, q=q, page_no=p,
                pages=max(1, -(-total // PER_PAGE)), total=total, counts=counts)


@router.get("/buyurtmalar/{order_id}")
def order_detail(request: Request, db: DB, admin: Admin, order_id: int):
    order = get_order(db, order_id)
    if order is None:
        raise HTTPException(404)
    return page(request, "order.html", admin, order=order)


@router.post("/buyurtmalar/{order_id}/holat")
async def order_status(request: Request, db: DB, admin: Admin, background: BackgroundTasks, order_id: int):
    form = await checked_form(request)
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404)
    value = str(form.get("status", ""))
    if value not in OrderStatus.__members__:
        raise HTTPException(400)
    order.status = OrderStatus(value)
    db.commit()
    background.add_task(refresh_order_message, order.id)
    flash(request, f"#{order.number} holati: {STATUS_LABELS[order.status]}")
    return redirect(f"/admin/buyurtmalar/{order.id}")


# ---------------- Mahsulotlar ----------------

def _refs(db: Session) -> dict:
    return {
        "categories": list(db.scalars(select(Category).order_by(Category.sort))),
        "crops": list(db.scalars(select(Crop).order_by(Crop.sort))),
        "problems": list(db.scalars(select(Problem).order_by(Problem.type, Problem.sort))),
        "pack_shapes": PACK_SHAPES,
        "shape_labels": SHAPE_LABELS,
        "problem_types": PROBLEM_TYPES,
    }


def _load_product(db: Session, product_id: int) -> Product:
    product = db.scalars(
        select(Product).where(Product.id == product_id).options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.usages).selectinload(ProductUsage.crop),
            selectinload(Product.usages).selectinload(ProductUsage.problem),
        )
    ).first()
    if product is None:
        raise HTTPException(404)
    return product


@router.get("/mahsulotlar")
def products_list(request: Request, db: DB, admin: Admin, q: str = "", cat: str = ""):
    query = select(Product).options(
        selectinload(Product.category), selectinload(Product.variants), selectinload(Product.images)
    )
    q = q.strip()[:100]
    if q:
        query = query.where(or_(Product.name_uz.ilike(f"%{q}%"), Product.name_ru.ilike(f"%{q}%"),
                                Product.registration_no.ilike(f"%{q}%")))
    if cat.isdigit():
        query = query.where(Product.category_id == int(cat))
    products = list(db.scalars(query.order_by(Product.is_active.desc(), Product.sort, Product.id)))
    return page(request, "products.html", admin, products=products, q=q, cat=cat,
                categories=list(db.scalars(select(Category).order_by(Category.sort))))


@router.get("/mahsulotlar/yangi")
def product_new(request: Request, db: DB, admin: Admin):
    return page(request, "product_form.html", admin, product=None,
                form=ProductForm.from_product(None), **_refs(db))


@router.post("/mahsulotlar/yangi")
async def product_create(request: Request, db: DB, admin: Admin):
    pf = ProductForm.from_form(await checked_form(request))
    product = pf.save(db, None)
    if product is None:
        return page(request, "product_form.html", admin, status_code=422, product=None, form=pf, **_refs(db))
    flash(request, "Mahsulot qo‘shildi. Endi rasm yuklashingiz mumkin.")
    return redirect(f"/admin/mahsulotlar/{product.id}")


@router.get("/mahsulotlar/{product_id}")
def product_edit(request: Request, db: DB, admin: Admin, product_id: int):
    product = _load_product(db, product_id)
    return page(request, "product_form.html", admin, product=product,
                form=ProductForm.from_product(product), **_refs(db))


@router.post("/mahsulotlar/{product_id}")
async def product_update(request: Request, db: DB, admin: Admin, product_id: int):
    product = _load_product(db, product_id)
    pf = ProductForm.from_form(await checked_form(request))
    if pf.save(db, product) is None:
        product = _load_product(db, product_id)
        return page(request, "product_form.html", admin, status_code=422, product=product, form=pf,
                    **_refs(db))
    flash(request, "Saqlandi.")
    return redirect(f"/admin/mahsulotlar/{product_id}")


@router.post("/mahsulotlar/{product_id}/rasm")
async def product_image_upload(request: Request, db: DB, admin: Admin, product_id: int):
    product = _load_product(db, product_id)
    form = await checked_form(request)
    upload = form.get("image")
    if not isinstance(upload, UploadFile) or not upload.filename:
        flash(request, "Rasm faylini tanlang.", "error")
        return redirect(f"/admin/mahsulotlar/{product_id}#rasmlar")
    content = await upload.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    try:
        url = media.save_image(product.id, content)
    except ValueError as exc:
        flash(request, str(exc), "error")
        return redirect(f"/admin/mahsulotlar/{product_id}#rasmlar")
    next_sort = max((i.sort for i in product.images), default=-1) + 1
    product.images.append(ProductImage(url=url, sort=next_sort))
    db.commit()
    flash(request, "Rasm yuklandi.")
    return redirect(f"/admin/mahsulotlar/{product_id}#rasmlar")


@router.post("/mahsulotlar/{product_id}/rasm/{image_id}")
async def product_image_action(request: Request, db: DB, admin: Admin, product_id: int, image_id: int):
    form = await checked_form(request)
    product = _load_product(db, product_id)
    image = next((i for i in product.images if i.id == image_id), None)
    if image is None:
        raise HTTPException(404)
    if form.get("action") == "delete":
        product.images.remove(image)
        db.commit()
        media.delete_image(image.url)
        flash(request, "Rasm o‘chirildi.")
    elif form.get("action") == "main":
        # Tanlangan rasm birinchi bo'ladi
        for n, img in enumerate(sorted(product.images, key=lambda i: (i.id != image_id, i.sort))):
            img.sort = n
        db.commit()
        flash(request, "Asosiy rasm o‘zgartirildi.")
    return redirect(f"/admin/mahsulotlar/{product_id}#rasmlar")


# ---------------- Narx va qoldiq ----------------

@router.get("/narxlar")
def prices_page(request: Request, db: DB, admin: Admin, cat: str = ""):
    query = (
        select(ProductVariant)
        .join(Product)
        .options(selectinload(ProductVariant.product).selectinload(Product.category))
        .order_by(Product.is_active.desc(), Product.sort, Product.id, ProductVariant.sort)
    )
    if cat.isdigit():
        query = query.where(Product.category_id == int(cat))
    return page(request, "prices.html", admin, variants=list(db.scalars(query)), cat=cat,
                categories=list(db.scalars(select(Category).order_by(Category.sort))),
                low_limit=LOW_STOCK)


@router.post("/narxlar")
async def prices_save(request: Request, db: DB, admin: Admin):
    form = await checked_form(request)
    ids = [int(k[2:]) for k in form if k.startswith("p-") and k[2:].isdigit()]
    variants = {v.id: v for v in db.scalars(select(ProductVariant).where(ProductVariant.id.in_(ids)))}
    changed, bad = 0, []
    for vid, variant in variants.items():
        price_raw = str(form.get(f"p-{vid}", "")).replace(" ", "").replace(" ", "")
        stock_raw = str(form.get(f"s-{vid}", "")).replace(" ", "")
        try:
            price = int(price_raw) if price_raw else None
            stock = int(stock_raw) if stock_raw else 0
            if (price is not None and price < 0) or stock < 0:
                raise ValueError
        except ValueError:
            bad.append(variant.pack_label)
            continue
        if variant.price != price or variant.stock != stock:
            variant.price, variant.stock = price, stock
            changed += 1
    if bad:
        db.rollback()
        flash(request, "Xato qiymat (faqat musbat butun son): " + ", ".join(bad), "error")
    else:
        db.commit()
        flash(request, f"Saqlandi: {changed} ta qadoq o‘zgardi.")
    return redirect(safe_next(str(form.get("next", "")), "/admin/narxlar"))


# ---------------- Ma'lumotnoma: kategoriya, ekin, muammo ----------------

@router.get("/malumotnoma")
def refs_page(request: Request, db: DB, admin: Admin):
    crops = list(db.scalars(select(Crop).options(selectinload(Crop.problems)).order_by(Crop.sort)))
    refs = {k: v for k, v in _refs(db).items() if k != "crops"}
    return page(request, "refs.html", admin, crops=crops, **refs)


@router.post("/kategoriya/{category_id}")
async def category_save(request: Request, db: DB, admin: Admin, category_id: int):
    form = await checked_form(request)
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(404)
    for f in ("name_uz", "name_ru", "short_uz", "short_ru", "description_uz", "description_ru"):
        value = str(form.get(f, "")).strip()
        if value or f.startswith("description"):
            setattr(cat, f, value)
    db.commit()
    flash(request, f"“{cat.name_uz}” saqlandi.")
    return redirect("/admin/malumotnoma#kategoriyalar")


def _ref_fields(form, *, need_type: bool = False) -> tuple[dict, list[str]]:
    data = {
        "slug": slugify(str(form.get("slug", "")) or str(form.get("name_uz", ""))),
        "name_uz": str(form.get("name_uz", "")).strip(),
        "name_ru": str(form.get("name_ru", "")).strip(),
        "sort": str(form.get("sort", "0")).strip(),
    }
    errors = []
    if not data["name_uz"]:
        errors.append("Nomi (UZ) majburiy.")
    if not data["slug"]:
        errors.append("Slug bo‘sh bo‘lmasligi kerak.")
    data["name_ru"] = data["name_ru"] or data["name_uz"]
    data["sort"] = int(data["sort"]) if data["sort"].lstrip("-").isdigit() else 0
    if need_type:
        t = str(form.get("type", ""))
        if t not in ProblemType.__members__:
            errors.append("Muammo turini tanlang.")
        else:
            data["type"] = ProblemType(t)
    return data, errors


def _ref_or_new(db: Session, model, raw_id: str):
    """/yangi — None (yangi yozuv); raqam — mavjud yozuv yoki 404."""
    if raw_id == "yangi":
        return None
    obj = db.get(model, int(raw_id)) if raw_id.isdigit() else None
    if obj is None:
        raise HTTPException(404)
    return obj


@router.get("/ekinlar/{crop_id}")
def crop_edit(request: Request, db: DB, admin: Admin, crop_id: str):
    crop = _ref_or_new(db, Crop, crop_id)
    linked = {p.id for p in crop.problems} if crop else set()
    return page(request, "crop_form.html", admin, crop=crop, linked=linked, **_refs(db))


@router.post("/ekinlar/{crop_id}")
async def crop_save(request: Request, db: DB, admin: Admin, crop_id: str):
    form = await checked_form(request)
    crop = _ref_or_new(db, Crop, crop_id)

    if form.get("action") == "delete" and crop:
        if db.scalar(select(exists().where(ProductUsage.crop_id == crop.id))):
            flash(request, "Bu ekinga mahsulotlar bog‘langan — avval ularni olib tashlang.", "error")
            return redirect(f"/admin/ekinlar/{crop.id}")
        db.delete(crop)
        db.commit()
        flash(request, "Ekin o‘chirildi.")
        return redirect("/admin/malumotnoma#ekinlar")

    data, errors = _ref_fields(form)
    color = str(form.get("color", "#9BD27E"))
    data["color"] = color if len(color) == 7 and color.startswith("#") else "#9BD27E"
    taken = db.scalar(select(Crop.id).where(Crop.slug == data["slug"]))
    if taken and (crop is None or taken != crop.id):
        errors.append(f"“{data['slug']}” slugi band.")
    if errors:
        flash(request, " ".join(errors), "error")
        return redirect(f"/admin/ekinlar/{crop_id}")
    if crop is None:
        crop = Crop()
        db.add(crop)
    for k, v in data.items():
        setattr(crop, k, v)
    db.flush()

    wanted = {int(x) for x in form.getlist("problems") if str(x).isdigit()}
    used = set(db.scalars(select(ProductUsage.problem_id).where(ProductUsage.crop_id == crop.id)))
    current = set(db.scalars(select(CropProblem.problem_id).where(CropProblem.crop_id == crop.id)))
    # Mahsulot bog'langan muammoni olib tashlab bo'lmaydi — aks holda tanlashda yo'qolib qoladi
    for pid in current - wanted - used:
        db.delete(db.get(CropProblem, (crop.id, pid)))
    for pid in (wanted | used) - current:
        db.add(CropProblem(crop_id=crop.id, problem_id=pid))
    db.commit()
    kept = (current - wanted) & used
    msg = "Ekin saqlandi."
    if kept:
        msg += " Mahsulot bog‘langan muammolar ro‘yxatda qoldirildi."
    flash(request, msg)
    return redirect(f"/admin/ekinlar/{crop.id}")


@router.get("/muammolar/{problem_id}")
def problem_edit(request: Request, db: DB, admin: Admin, problem_id: str):
    problem = _ref_or_new(db, Problem, problem_id)
    return page(request, "problem_form.html", admin, problem=problem, problem_types=PROBLEM_TYPES)


@router.post("/muammolar/{problem_id}")
async def problem_save(request: Request, db: DB, admin: Admin, problem_id: str):
    form = await checked_form(request)
    problem = _ref_or_new(db, Problem, problem_id)

    if form.get("action") == "delete" and problem:
        if db.scalar(select(exists().where(ProductUsage.problem_id == problem.id))):
            flash(request, "Bu muammoga mahsulotlar bog‘langan — avval ularni olib tashlang.", "error")
            return redirect(f"/admin/muammolar/{problem.id}")
        for link in db.scalars(select(CropProblem).where(CropProblem.problem_id == problem.id)):
            db.delete(link)
        db.delete(problem)
        db.commit()
        flash(request, "Muammo o‘chirildi.")
        return redirect("/admin/malumotnoma#muammolar")

    data, errors = _ref_fields(form, need_type=True)
    taken = db.scalar(select(Problem.id).where(Problem.slug == data["slug"]))
    if taken and (problem is None or taken != problem.id):
        errors.append(f"“{data['slug']}” slugi band.")
    if errors:
        flash(request, " ".join(errors), "error")
        return redirect(f"/admin/muammolar/{problem_id}")
    if problem is None:
        problem = Problem()
        db.add(problem)
    for k, v in data.items():
        setattr(problem, k, v)
    db.commit()
    flash(request, "Muammo saqlandi. Uni ekinlarga ekin sahifasida bog‘lang.")
    return redirect(f"/admin/muammolar/{problem.id}")

