# Yashil Dala — agro mahsulotlar sotish sayti

Bu fayl claude.ai chatidagi rejalashtirish natijasi. Ishni shu yerdan davom ettiring.
Foydalanuvchi bilan **o‘zbek tilida** (lotin) gaplashing.

## Loyiha nima

Foydalanuvchi o‘z mahsulotlarini onlayn sotadi:
- o‘g‘itlar va o‘sish stimulyatorlari (ekin va sabzavotlar uchun);
- o‘simlik himoyasi: zararkunanda va kasalliklarga qarshi vositalar (insektitsid, fungitsid, akaritsid);
- uy uchun vositalar (tarakan, chumoli).

“Yashil Dala” — vaqtinchalik nom, keyin almashtiriladi.

## Asosiy funksiya: “Muammo bo‘yicha tanlash”

Fermer dori nomini emas, muammoni biladi. Oqim:
1. Ekinni tanlaydi (pomidor, bodring, olma, uzum, kartoshka, g‘o‘za, piyoz, uy-joy).
2. Shu ekinga tegishli muammoni tanlaydi (shira, trips, o‘rgimchakkana, fitoftoroz, un-shudring, sekin o‘sish, barglar sarg‘ayishi…).
3. Sayt **faqat shu ekin uchun ro‘yxatdan o‘tgan** va shu muammoga qarshi vositalarni ko‘rsatadi.
4. Mos mahsulot bo‘lmasa — “mutaxassisga yozish” holati chiqadi.

Bu qonuniy talab ham: litsenziya bir ekinga ro‘yxatdan o‘tgan dorini boshqa ekinga qo‘llashga yo‘l qo‘ymaydi. Shuning uchun tanlash `product_usages` jadvalidan (mahsulot × ekin × muammo) olinadi.

## Dizayn

`design/` papkasida 8 ta ekran bor (claude.ai'dagi “Yashil Dala — sayt dizayni” kanvasidan). Bular **dizayn kanvasining manba fayllari** — maxsus teglar (`<x-dc>`, `<sc-for>`, `<sc-if>`) va runtime’ga bog‘liq, to‘g‘ridan-to‘g‘ri ishga tushmaydi. Markup, matn, ranglar va o‘lchamlar uchun **namuna** sifatida ishlating.

| Fayl | Ekran |
|---|---|
| `Main.dc.html` | Bosh sahifa (telefon) |
| `Tanlash.dc.html` | Muammo bo‘yicha tanlash — logikasi `<script>` ichida (ekin→muammo→natija ma’lumotlari) |
| `Katalog.dc.html` | Katalog: qidiruv, kategoriya tablari, filtrlar, mahsulot kartochkalari |
| `Mahsulot.dc.html` | Mahsulot sahifasi: qadoq tanlash, ruxsat etilgan ekinlar va doza jadvali, qo‘llash, xavfsizlik |
| `Buyurtma.dc.html` | Savatcha + buyurtma formasi |
| `Tasdiq.dc.html` | Buyurtma qabul qilindi |
| `Bot.dc.html` | Do‘kon egasining Telegram botiga keladigan xabar namunasi |
| `Desktop.dc.html` | Bosh sahifa (kompyuter, moslashuvchan) |

Dizayn qoidalari:
- **Telefon birinchi** (mobile-first), keyin kompyuter.
- Shriftlar (Google Fonts): sarlavhalar — **Unbounded** 600; matn — **Onest** 400–700. Ikkalasi ham kirill harflarini qo‘llaydi (ruscha versiya uchun).
- Ranglar:
  - fon `#F4F5EF`, kartochka `#FFFFFF`, chegara `#DCE2D8`
  - matn `#16241B`, ikkinchi darajali matn `#4D5C52`
  - asosiy yashil `#1E5B3A` (to‘q qismi `#143F28`), och yashil `#E3EFE5`
  - urg‘u (CTA) bug‘doy-sariq `#E7A93B`, ustida to‘q matn
  - kategoriya ranglari: o‘g‘it — `#E3EFE5`/`#1E5B3A`; himoya — `#FBF0D9`/`#7A4A06`; uy uchun — `#E5ECF3`/`#24486B`
  - footer `#16241B`, undagi matn `#B9C4BC`
- Burchaklar 12–20px, tugma va bosiladigan joylar kamida 44px.
- Emoji ishlatilmaydi; ikonkalar — inline stroke SVG.
- Narx, doza, guvohnoma raqami, telefon, manzil hozircha `[narx]`, `[doza]`, `[raqam]` kabi bo‘sh joylar — ular bazadan keladi.

## Tillar

O‘zbekcha (lotin) va ruscha, har sahifada UZ/RU almashtirgich. Matnlar alohida tarjima fayllarida yoki bazada `name_uz`/`name_ru` ustunlarida.

## Texnik stek

- Backend: **FastAPI + PostgreSQL** (foydalanuvchi backendni yaxshi biladi).
- Frontend: **FastAPI + Jinja2** shablonlari (tanlangan). Sahifalar serverda chiziladi, JS faqat progressiv qulaylik uchun — sayt JS'siz ham ishlashi kerak.
- Migratsiyalar: Alembic (`migrations/`). Testlar: pytest, SQLite'da (`tests/`).
- Git: Claude sessiyasida bu repoga push ruxsati bo‘lmasligi mumkin — unda o‘zgarishlar git bundle qilib beriladi, foydalanuvchi o‘zi push qiladi.
- Admin panel: mahsulot, narx, qoldiq va buyurtmalarni boshqarish.

## Ma’lumotlar bazasi (dastlabki sxema)

- `categories` — id, slug, name_uz, name_ru
- `products` — id, slug, category_id, name_uz/ru, description_uz/ru, active_ingredient, registration_no (davlat guvohnomasi), manufacturer, waiting_days (kutish muddati), mxik_code, safety_uz/ru, usage_uz/ru, is_active
- `product_variants` — id, product_id, pack_label (250 ml, 1 L…), price, stock
- `product_images` — id, product_id, url, sort
- `crops` — id, slug, name_uz/ru, color
- `problems` — id, slug, name_uz/ru, type (`pest` | `disease` | `nutrition` | `household`)
- `crop_problems` — crop_id, problem_id (har ekin uchun qaysi muammolar ko‘rsatiladi)
- `product_usages` — product_id, crop_id, problem_id, dose_text, note — **unique (product, crop, problem)**; tanlash funksiyasi va qonuniy cheklov shu jadvalda
- `orders` — id, number, customer_name, phone, region, address, delivery_method (`delivery` | `pickup`), comment, status (`new` | `accepted` | `called` | `delivered` | `cancelled`), total, consent_at, telegram_message_id, created_at
- `order_items` — order_id, variant_id, qty, unit_price

Tanlash so‘rovi: `products` ⋈ `product_usages` WHERE crop_id = ? AND problem_id = ? AND is_active.

## Buyurtma oqimi

1. Mijoz savatcha → forma (ism, telefon +998, viloyat, manzil, olish usuli, izoh, shaxsiy ma’lumotlarga rozilik belgisi).
2. Buyurtma bazaga yoziladi.
3. Telegram bot do‘kon egasining chatiga xabar yuboradi (namuna: `design/Bot.dc.html`), inline tugmalar bilan: “Qabul qilish”, “Qo‘ng‘iroq qildim”, “Bekor qilish”. Tugma bosilganda `orders.status` yangilanadi va xabar tahrirlanadi.
4. To‘lov hozircha **qabul qilganda** (naqd/karta). Onlayn to‘lov (Click/Payme) keyinroq — buning uchun `mxik_code` maydoni hozirdan bor.

## Joylashtirish (keyinroq)

- Foydalanuvchining VPS’i, Docker; Caddy avtomatik HTTPS beradi.
- Oldiga Cloudflare (bepul tarif), bazaning kunlik zaxira nusxasi serverdan tashqarida.
- `.uz` domen.

## Hal qilinmagan masalalar

- Haqiqiy brend nomi, logotip.
- Haqiqiy mahsulotlar ro‘yxati — foydalanuvchi keyin Excel/CSV shaklida beradi; import skripti kerak bo‘ladi.
- Litsenziya va mahsulot guvohnomalari — foydalanuvchi o‘zi hal qilmoqda; sayt har mahsulotda guvohnoma raqamini, footerda litsenziya raqamini ko‘rsatadi.

## Holat

Bajarildi (1-bosqich):
- Loyiha strukturasi, modellar (yuqoridagi sxema + `kind_*`, `pack_shape`, `is_popular`, `sort`, `orders.lang`, `orders.delivery_price`), Alembic boshlang‘ich migratsiyasi.
- `design/` dagi barcha ekranlar Jinja2'da: bosh sahifa (telefon + kompyuter), tanlash, katalog, mahsulot, savatcha/forma, tasdiq, 404. UZ/RU.
- Savatcha (sessiya cookie), buyurtma yaratish, Telegram xabari va holat tugmalari (webhook).
- Namunaviy ma’lumotlar: `python -m scripts.seed`. Narx/doza/guvohnoma bo‘sh — saytda `[narx]`, `[doza]` ko‘rinadi.

Bajarildi (2-bosqich) — admin panel `/admin` (`app/admin/`):
- Kirish: `admin_users` jadvali, scrypt xesh, CSRF, urinishlar cheklovi; admin yaratish: `python -m scripts.create_admin LOGIN`.
- Buyurtmalar (filtr, qidiruv, holat → Telegram xabari ham yangilanadi), mahsulotlar (qadoqlar, ekin×muammo×doza, rasmlar), narx va qoldiq jadvali, ma’lumotnoma (ekin, muammo, kategoriya).
- Qoida: mahsulotga ekin×muammo qo‘shilsa, `crop_problems` ga ham avtomatik qo‘shiladi; mahsulot bog‘langan juftlikni ekin sahifasidan olib tashlab bo‘lmaydi.
- Admin interfeysi faqat o‘zbekcha.

Keyingi qadamlar:
- Excel/CSV import skripti (foydalanuvchi mahsulotlar ro‘yxatini beradi).
- “Yetkazib berish”, “Biz haqimizda” sahifalari (hozir bosh sahifadagi bo‘limlarga havola).
- Buyurtmada qoldiqni (`stock`) kamaytirish — hozir faqat `stock > 0` tekshiriladi.
- Joylashtirish: Caddy + Cloudflare, bazaning zaxira nusxasi.
