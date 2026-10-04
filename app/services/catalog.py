from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Crop, Problem, Product, ProductUsage, ProductVariant


def _product_query() -> Select[tuple[Product]]:
    return (
        select(Product)
        .where(Product.is_active.is_(True))
        .options(
            selectinload(Product.category),
            selectinload(Product.variants),
            selectinload(Product.images),
        )
    )


def categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.sort)))


def crops(db: Session) -> list[Crop]:
    return list(db.scalars(select(Crop).options(selectinload(Crop.problems)).order_by(Crop.sort)))


def popular_products(db: Session, limit: int = 4) -> list[Product]:
    q = _product_query().where(Product.is_popular.is_(True)).order_by(Product.sort).limit(limit)
    return list(db.scalars(q))


def search_products(
    db: Session,
    *,
    category: Category | None = None,
    crop: Crop | None = None,
    text: str = "",
    sort: str = "popular",
) -> list[Product]:
    q = _product_query()
    if category:
        q = q.where(Product.category_id == category.id)
    if crop:
        q = q.where(
            Product.id.in_(select(ProductUsage.product_id).where(ProductUsage.crop_id == crop.id))
        )
    text = text.strip()
    if text:
        like = f"%{text}%"
        problem_match = (
            select(ProductUsage.product_id)
            .join(Problem, Problem.id == ProductUsage.problem_id)
            .where(or_(Problem.name_uz.ilike(like), Problem.name_ru.ilike(like)))
        )
        q = q.where(
            or_(
                Product.name_uz.ilike(like),
                Product.name_ru.ilike(like),
                Product.active_ingredient.ilike(like),
                Product.id.in_(problem_match),
            )
        )

    min_price = (
        select(func.min(ProductVariant.price))
        .where(ProductVariant.product_id == Product.id)
        .scalar_subquery()
    )
    if sort == "price_asc":
        q = q.order_by(min_price.asc().nulls_last(), Product.sort)
    elif sort == "price_desc":
        q = q.order_by(min_price.desc().nulls_last(), Product.sort)
    elif sort == "name":
        q = q.order_by(Product.name_uz)
    else:
        q = q.order_by(Product.is_popular.desc(), Product.sort)
    return list(db.scalars(q))


def product_by_slug(db: Session, slug: str) -> Product | None:
    q = _product_query().where(Product.slug == slug).options(
        selectinload(Product.usages).selectinload(ProductUsage.crop),
        selectinload(Product.usages).selectinload(ProductUsage.problem),
    )
    return db.scalars(q).first()


def find_for_problem(db: Session, crop: Crop, problem: Problem) -> list[tuple[Product, ProductUsage]]:
    """Asosiy tanlash so'rovi: faqat shu ekin uchun ro'yxatdan o'tgan va shu muammoga qarshi."""
    q = (
        select(Product, ProductUsage)
        .join(ProductUsage, ProductUsage.product_id == Product.id)
        .where(
            ProductUsage.crop_id == crop.id,
            ProductUsage.problem_id == problem.id,
            Product.is_active.is_(True),
        )
        .options(selectinload(Product.category), selectinload(Product.variants))
        .order_by(Product.sort)
    )
    return [(p, u) for p, u in db.execute(q)]


def usage_table(product: Product, lang: str) -> list[dict]:
    """Mahsulot sahifasidagi jadval: ekin bo'yicha guruhlangan muammolar va doza."""
    rows: dict[int, dict] = {}
    for u in sorted(product.usages, key=lambda u: (u.crop.sort, u.problem.sort)):
        row = rows.setdefault(u.crop_id, {"crop": u.crop.t("name", lang), "problems": [], "doses": []})
        row["problems"].append(u.problem.t("name", lang))
        if u.dose_text and u.dose_text not in row["doses"]:
            row["doses"].append(u.dose_text)
    return list(rows.values())
