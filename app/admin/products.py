"""Mahsulot formasi: forma ↔ model, qadoqlar va ekin×muammo×doza qatorlari."""

import re
from dataclasses import dataclass, field

from sqlalchemy import exists, select
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.models import CropProblem, OrderItem, Product, ProductUsage, ProductVariant

TEXT_FIELDS = (
    "name_uz", "name_ru", "kind_uz", "kind_ru", "description_uz", "description_ru",
    "usage_uz", "usage_ru", "safety_uz", "safety_ru",
)
OPTIONAL_FIELDS = ("active_ingredient", "registration_no", "manufacturer", "mxik_code")
PACK_SHAPES = ("bottle", "bag", "tube")
BLANK_VARIANTS = 2
BLANK_USAGES = 3

_TRANSLIT = str.maketrans({"‘": "", "’": "", "'": "", "ʻ": "", "ʼ": "", "`": ""})


def slugify(text: str) -> str:
    text = text.translate(_TRANSLIT).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:120]


def _int_or_none(value: str) -> int | None:
    value = re.sub(r"[\s ]", "", value or "")
    if value == "":
        return None
    number = int(value)  # ValueError — chaqiruvchi ushlaydi
    if number < 0:
        raise ValueError
    return number


def _count(value: str, limit: int) -> int:
    return min(int(value), limit) if value.isdigit() else 0


@dataclass
class ProductForm:
    data: dict = field(default_factory=dict)
    variants: list[dict] = field(default_factory=list)
    usages: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # ---------- Modeldan ----------
    @classmethod
    def from_product(cls, product: Product | None) -> "ProductForm":
        form = cls()
        if product is None:
            form.data = {f: "" for f in (*TEXT_FIELDS, *OPTIONAL_FIELDS)}
            form.data.update(
                slug="", category_id="", waiting_days="", pack_shape="bottle",
                is_popular=False, is_active=True, sort="0",
            )
        else:
            form.data = {f: getattr(product, f) or "" for f in (*TEXT_FIELDS, *OPTIONAL_FIELDS)}
            form.data.update(
                slug=product.slug,
                category_id=str(product.category_id),
                waiting_days="" if product.waiting_days is None else str(product.waiting_days),
                pack_shape=product.pack_shape,
                is_popular=product.is_popular,
                is_active=product.is_active,
                sort=str(product.sort),
            )
            form.variants = [
                {"id": str(v.id), "pack_label": v.pack_label,
                 "price": "" if v.price is None else str(v.price),
                 "stock": str(v.stock), "delete": False}
                for v in product.variants
            ]
            form.usages = [
                {"id": str(u.id), "crop_id": str(u.crop_id), "problem_id": str(u.problem_id),
                 "dose_text": u.dose_text or "", "note": u.note or "", "delete": False}
                for u in sorted(product.usages, key=lambda u: (u.crop.sort, u.problem.sort))
            ]
        form.add_blank_rows()
        return form

    def add_blank_rows(self) -> None:
        self.variants += [
            {"id": "", "pack_label": "", "price": "", "stock": "", "delete": False}
            for _ in range(BLANK_VARIANTS)
        ]
        self.usages += [
            {"id": "", "crop_id": "", "problem_id": "", "dose_text": "", "note": "", "delete": False}
            for _ in range(BLANK_USAGES)
        ]

    # ---------- Formadan ----------
    @classmethod
    def from_form(cls, form: FormData) -> "ProductForm":
        def get(name: str) -> str:
            value = form.get(name, "")
            return value.strip() if isinstance(value, str) else ""

        pf = cls()
        pf.data = {f: get(f) for f in (*TEXT_FIELDS, *OPTIONAL_FIELDS)}
        pf.data.update(
            slug=get("slug"),
            category_id=get("category_id"),
            waiting_days=get("waiting_days"),
            pack_shape=get("pack_shape") if get("pack_shape") in PACK_SHAPES else "bottle",
            is_popular=bool(form.get("is_popular")),
            is_active=bool(form.get("is_active")),
            sort=get("sort") or "0",
        )
        for i in range(_count(get("v_count"), 100)):
            pf.variants.append({
                "id": get(f"v-{i}-id"), "pack_label": get(f"v-{i}-pack"),
                "price": get(f"v-{i}-price"), "stock": get(f"v-{i}-stock"),
                "delete": bool(form.get(f"v-{i}-delete")),
            })
        for i in range(_count(get("u_count"), 500)):
            pf.usages.append({
                "id": get(f"u-{i}-id"), "crop_id": get(f"u-{i}-crop"),
                "problem_id": get(f"u-{i}-problem"), "dose_text": get(f"u-{i}-dose"),
                "note": get(f"u-{i}-note"), "delete": bool(form.get(f"u-{i}-delete")),
            })
        return pf

    # ---------- Tekshirish va saqlash ----------
    def save(self, db: Session, product: Product | None) -> Product | None:
        """Xato bo'lsa self.errors to'ladi va None qaytadi (hech narsa saqlanmaydi)."""
        d = self.data
        e = self.errors
        if not d["name_uz"]:
            e.append("Nomi (UZ) majburiy.")
        slug = slugify(d["slug"] or d["name_uz"])
        if not slug:
            e.append("Slug (manzil) bo‘sh bo‘lmasligi kerak.")
        else:
            taken = db.scalar(select(Product.id).where(Product.slug == slug))
            if taken and (product is None or taken != product.id):
                e.append(f"“{slug}” manzili boshqa mahsulotda band.")
        d["slug"] = slug
        try:
            category_id = int(d["category_id"])
        except ValueError:
            category_id = 0
            e.append("Kategoriyani tanlang.")
        try:
            waiting_days = _int_or_none(d["waiting_days"])
        except ValueError:
            waiting_days = None
            e.append("Kutish muddati — musbat butun son (kun).")
        try:
            sort = int(d["sort"])
        except ValueError:
            sort = 0

        variants = self._parse_variants()
        usages = self._parse_usages()
        if not any(not v["delete"] for v in variants):
            e.append("Kamida bitta qadoq (hajm) bo‘lishi kerak.")
        if e:
            return None

        if product is None:
            product = Product()
            db.add(product)
        for f in TEXT_FIELDS:
            setattr(product, f, d[f])
        if not product.name_ru:
            product.name_ru = d["name_uz"]
        for f in OPTIONAL_FIELDS:
            setattr(product, f, d[f] or None)
        product.slug = slug
        product.category_id = category_id
        product.waiting_days = waiting_days
        product.pack_shape = d["pack_shape"]
        product.is_popular = d["is_popular"]
        product.is_active = d["is_active"]
        product.sort = sort
        db.flush()

        if not self._apply_variants(db, product, variants) or not self._apply_usages(db, product, usages):
            db.rollback()
            return None
        db.commit()
        return product

    def _parse_variants(self) -> list[dict]:
        rows = []
        for n, row in enumerate(self.variants, 1):
            if not row["id"] and not row["pack_label"]:
                continue  # bo'sh yangi qator
            if not row["pack_label"] and not row["delete"]:
                self.errors.append(f"Qadoq {n}: hajmini yozing (masalan, 1 L).")
                continue
            try:
                price = _int_or_none(row["price"])
                stock = _int_or_none(row["stock"]) or 0
            except ValueError:
                self.errors.append(f"Qadoq “{row['pack_label']}”: narx va qoldiq — musbat butun son.")
                continue
            rows.append({**row, "price": price, "stock": stock, "sort": n})
        return rows

    def _parse_usages(self) -> list[dict]:
        rows, seen = [], set()
        for n, row in enumerate(self.usages, 1):
            if not row["id"] and not (row["crop_id"] or row["problem_id"]):
                continue
            if row["delete"]:
                rows.append(row)
                continue
            try:
                key = (int(row["crop_id"]), int(row["problem_id"]))
            except ValueError:
                self.errors.append(f"Qo‘llanish {n}: ekin va muammoni tanlang.")
                continue
            if key in seen:
                self.errors.append(f"Qo‘llanish {n}: bu ekin va muammo jadvalda takrorlangan.")
                continue
            seen.add(key)
            rows.append({**row, "crop_id": key[0], "problem_id": key[1]})
        return rows

    def _apply_variants(self, db: Session, product: Product, rows: list[dict]) -> bool:
        existing = {v.id: v for v in product.variants}
        for row in rows:
            if not row["id"]:
                if not row["delete"]:
                    product.variants.append(ProductVariant(
                        pack_label=row["pack_label"], price=row["price"],
                        stock=row["stock"], sort=row["sort"],
                    ))
                continue
            variant = existing.get(int(row["id"]))
            if variant is None:
                continue
            if row["delete"]:
                used = db.scalar(select(exists().where(OrderItem.variant_id == variant.id)))
                if used:
                    self.errors.append(
                        f"“{variant.pack_label}” qadog‘i buyurtmalarda bor — o‘chirib bo‘lmaydi. "
                        "Qoldig‘ini 0 qiling."
                    )
                    return False
                product.variants.remove(variant)
                continue
            variant.pack_label = row["pack_label"]
            variant.price = row["price"]
            variant.stock = row["stock"]
            variant.sort = row["sort"]
        return True

    def _apply_usages(self, db: Session, product: Product, rows: list[dict]) -> bool:
        existing = {u.id: u for u in product.usages}
        # Avval o'chirish: shu formada qayta qo'shilgan juftlik unique'ga urilmasin
        for row in rows:
            if row["id"] and row["delete"] and int(row["id"]) in existing:
                product.usages.remove(existing.pop(int(row["id"])))
        db.flush()
        for row in rows:
            if row["delete"]:
                continue
            if row["id"] and int(row["id"]) in existing:
                usage = existing[int(row["id"])]
            else:
                usage = ProductUsage()
                product.usages.append(usage)
            usage.crop_id = row["crop_id"]
            usage.problem_id = row["problem_id"]
            usage.dose_text = row["dose_text"] or None
            usage.note = row["note"] or None
            ensure_crop_problem(db, row["crop_id"], row["problem_id"])
        return True


def ensure_crop_problem(db: Session, crop_id: int, problem_id: int) -> None:
    """Qo'llanish qo'shilsa, muammo shu ekin ro'yxatida ham ko'rinsin."""
    if db.get(CropProblem, (crop_id, problem_id)) is None:
        db.add(CropProblem(crop_id=crop_id, problem_id=problem_id))
