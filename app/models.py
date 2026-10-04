from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ProblemType(StrEnum):
    pest = "pest"
    disease = "disease"
    nutrition = "nutrition"
    household = "household"


class DeliveryMethod(StrEnum):
    delivery = "delivery"
    pickup = "pickup"


class OrderStatus(StrEnum):
    new = "new"
    accepted = "accepted"
    called = "called"
    delivered = "delivered"
    cancelled = "cancelled"


class LocalizedMixin:
    """`obj.t("name", lang)` — name_uz / name_ru ustunidan matn qaytaradi."""

    def t(self, field: str, lang: str) -> str:
        value = getattr(self, f"{field}_{lang}", None)
        return value or getattr(self, f"{field}_uz", None) or ""


class Category(LocalizedMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name_uz: Mapped[str] = mapped_column(String(200))
    name_ru: Mapped[str] = mapped_column(String(200))
    short_uz: Mapped[str] = mapped_column(String(64), default="")
    short_ru: Mapped[str] = mapped_column(String(64), default="")
    description_uz: Mapped[str] = mapped_column(String(300), default="")
    description_ru: Mapped[str] = mapped_column(String(300), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(LocalizedMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    name_uz: Mapped[str] = mapped_column(String(300))
    name_ru: Mapped[str] = mapped_column(String(300))
    kind_uz: Mapped[str] = mapped_column(String(100), default="")  # Insektitsid, Fungitsid…
    kind_ru: Mapped[str] = mapped_column(String(100), default="")
    description_uz: Mapped[str] = mapped_column(Text, default="")
    description_ru: Mapped[str] = mapped_column(Text, default="")
    active_ingredient: Mapped[str | None] = mapped_column(String(300))
    registration_no: Mapped[str | None] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    waiting_days: Mapped[int | None] = mapped_column(Integer)
    mxik_code: Mapped[str | None] = mapped_column(String(32))
    # Bir qatorda bitta band (\n bilan ajratilgan)
    safety_uz: Mapped[str] = mapped_column(Text, default="")
    safety_ru: Mapped[str] = mapped_column(Text, default="")
    usage_uz: Mapped[str] = mapped_column(Text, default="")
    usage_ru: Mapped[str] = mapped_column(Text, default="")
    # Rasm yo'q paytda ko'rsatiladigan qadoq shakli: bottle | bag | tube
    pack_shape: Mapped[str] = mapped_column(String(16), default="bottle")
    is_popular: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped[Category] = relationship(back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", order_by="ProductVariant.sort", cascade="all, delete-orphan"
    )
    images: Mapped[list["ProductImage"]] = relationship(
        order_by="ProductImage.sort", cascade="all, delete-orphan"
    )
    usages: Mapped[list["ProductUsage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    def lines(self, field: str, lang: str) -> list[str]:
        return [line.strip() for line in self.t(field, lang).splitlines() if line.strip()]

    @property
    def min_price(self) -> int | None:
        prices = [v.price for v in self.variants if v.price is not None]
        return min(prices) if prices else None


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    pack_label: Mapped[str] = mapped_column(String(50))
    price: Mapped[int | None] = mapped_column(Integer)  # so'm; None = hali belgilanmagan
    stock: Mapped[int] = mapped_column(Integer, default=0)
    sort: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="variants")


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(500))
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Crop(LocalizedMixin, Base):
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name_uz: Mapped[str] = mapped_column(String(100))
    name_ru: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(16), default="#9BD27E")
    sort: Mapped[int] = mapped_column(Integer, default=0)

    problems: Mapped[list["Problem"]] = relationship(
        secondary="crop_problems", order_by="Problem.sort"
    )


class Problem(LocalizedMixin, Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name_uz: Mapped[str] = mapped_column(String(100))
    name_ru: Mapped[str] = mapped_column(String(100))
    type: Mapped[ProblemType] = mapped_column(Enum(ProblemType, name="problem_type"))
    sort: Mapped[int] = mapped_column(Integer, default=0)


class CropProblem(Base):
    __tablename__ = "crop_problems"

    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"), primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True
    )


class ProductUsage(Base):
    """Mahsulot × ekin × muammo: dori faqat shu yerda yozilgan ekinlarga tavsiya qilinadi."""

    __tablename__ = "product_usages"
    __table_args__ = (UniqueConstraint("product_id", "crop_id", "problem_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"))
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    dose_text: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(String(300))

    product: Mapped[Product] = relationship(back_populates="usages")
    crop: Mapped[Crop] = relationship()
    problem: Mapped[Problem] = relationship()


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str | None] = mapped_column(String(20), unique=True)  # id dan: 0001
    customer_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))
    region: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(Text, default="")
    delivery_method: Mapped[DeliveryMethod] = mapped_column(
        Enum(DeliveryMethod, name="delivery_method")
    )
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.new
    )
    delivery_price: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    lang: Mapped[str] = mapped_column(String(2), default="uz")
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    telegram_message_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(Integer, default=0)

    order: Mapped[Order] = relationship(back_populates="items")
    variant: Mapped[ProductVariant] = relationship()


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
