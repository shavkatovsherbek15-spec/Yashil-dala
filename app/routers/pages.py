from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.i18n import LANGS
from app.models import Category, Crop
from app.services import catalog
from app.web import get_lang, render, safe_next

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]

SORTS = ("popular", "price_asc", "price_desc", "name")


def _crop_problem_map(crops: list[Crop], lang: str) -> dict[str, list[dict]]:
    return {
        c.slug: [{"slug": p.slug, "name": p.t("name", lang)} for p in c.problems] for c in crops
    }


@router.get("/")
def home(request: Request, db: DB):
    lang = get_lang(request)
    crops = catalog.crops(db)
    return render(
        request,
        "home.html",
        {
            "crops": crops,
            "crop_problems": _crop_problem_map(crops, lang),
            "categories": catalog.categories(db),
            "popular": catalog.popular_products(db),
        },
    )


@router.get("/tanlash")
def select_by_problem(request: Request, db: DB, crop: str = "", problem: str = ""):
    crops = catalog.crops(db)
    crop_obj = next((c for c in crops if c.slug == crop), None)
    problem_obj = None
    if crop_obj and problem:
        # Muammo shu ekin ro'yxatida bo'lishi shart
        problem_obj = next((p for p in crop_obj.problems if p.slug == problem), None)
    results = catalog.find_for_problem(db, crop_obj, problem_obj) if problem_obj else []
    return render(
        request,
        "select.html",
        {"crops": crops, "crop": crop_obj, "problem": problem_obj, "results": results},
    )


@router.get("/katalog")
def catalog_page(
    request: Request, db: DB, cat: str = "", crop: str = "", q: str = "", sort: str = "popular"
):
    category = db.scalars(select(Category).where(Category.slug == cat)).first() if cat else None
    crop_obj = db.scalars(select(Crop).where(Crop.slug == crop)).first() if crop else None
    sort = sort if sort in SORTS else "popular"
    products = catalog.search_products(db, category=category, crop=crop_obj, text=q[:100], sort=sort)
    return render(
        request,
        "catalog.html",
        {
            "categories": catalog.categories(db),
            "crops": catalog.crops(db),
            "category": category,
            "crop": crop_obj,
            "q": q[:100],
            "sort": sort,
            "sorts": SORTS,
            "products": products,
        },
    )


@router.get("/mahsulot/{slug}")
def product_page(request: Request, db: DB, slug: str, v: int | None = None):
    product = catalog.product_by_slug(db, slug)
    if product is None:
        raise HTTPException(404)
    in_stock = [x for x in product.variants if x.stock > 0]
    variant = next((x for x in in_stock if x.id == v), None) or next(
        iter(in_stock or product.variants), None
    )
    return render(
        request,
        "product.html",
        {
            "product": product,
            "variant": variant,
            "usage_rows": catalog.usage_table(product, get_lang(request)),
        },
    )


@router.get("/til/{code}")
def switch_lang(code: str, next: str = "/"):
    response = RedirectResponse(safe_next(next), status_code=303)
    if code in LANGS:
        response.set_cookie("lang", code, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response

