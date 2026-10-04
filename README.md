# Yashil Dala — agro mahsulotlar do‘koni

FastAPI + Jinja2 + PostgreSQL. Sahifalar serverda chiziladi, JavaScript faqat qulaylik uchun
(sayt JS'siz ham to‘liq ishlaydi). Loyiha haqidagi asosiy qarorlar — `CLAUDE.md` da.

## Ishga tushirish (lokal)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env

docker compose up -d db          # yoki o'zingizning PostgreSQL
alembic upgrade head             # jadvallarni yaratish
python -m scripts.seed           # namunaviy ma'lumotlar
python -m scripts.create_admin admin   # admin panel uchun login (parol so'raladi)
uvicorn app.main:app --reload    # http://127.0.0.1:8000, admin: /admin
```

Hammasini Docker'da: `docker compose up --build`, keyin
`docker compose exec web python -m scripts.seed` va
`docker compose exec web python -m scripts.create_admin admin`.

Testlar (SQLite'da, Postgres shart emas): `pytest`

## Sahifalar

| URL | Ekran (`design/`) |
|---|---|
| `/` | Bosh sahifa — telefon va kompyuter (`Main`, `Desktop`) |
| `/tanlash?crop=…&problem=…` | Muammo bo‘yicha tanlash (`Tanlash`) |
| `/katalog?cat=…&crop=…&q=…&sort=…` | Katalog (`Katalog`) |
| `/mahsulot/{slug}` | Mahsulot (`Mahsulot`) |
| `/savatcha` | Savatcha + buyurtma formasi (`Buyurtma`) |
| `/buyurtma/{id}` | Buyurtma qabul qilindi (`Tasdiq`) |
| `/til/uz`, `/til/ru` | Tilni almashtirish (cookie) |
| `POST /telegram/webhook` | Bot tugmalari (`Bot`) |
| `/admin` | Admin panel (quyida) |

## Admin panel (`/admin`)

- **Bosh sahifa** — yangi buyurtmalar, qoldig‘i kam (≤ 5) qadoqlar, narxsiz qadoqlar soni.
- **Buyurtmalar** — holat bo‘yicha filtr, raqam/telefon/ism bo‘yicha qidiruv; holatni o‘zgartirish
  Telegramdagi xabarni ham yangilaydi.
- **Mahsulotlar** — UZ/RU matnlar, guvohnoma, qadoqlar (narx, qoldiq), ekin × muammo × doza jadvali,
  rasmlar (JPG/PNG/WEBP; turi fayl ichidan tekshiriladi). Buyurtmada bor qadoqni o‘chirib bo‘lmaydi.
- **Narx va qoldiq** — barcha qadoqlar bitta jadvalda.
- **Ma’lumotnoma** — ekinlar (va ularda ko‘rinadigan muammolar), muammolar, kategoriyalar.

Xavfsizlik: parol scrypt bilan saqlanadi, barcha POST formalarda CSRF token, IP bo‘yicha 15 daqiqada
5 ta noto‘g‘ri urinishdan keyin bloklanadi, 12 soat harakatsizlikdan keyin qayta kirish kerak.
Ishlab chiqarishda `SECRET_KEY` ni almashtiring va `SESSION_HTTPS_ONLY=true` qiling.

## Tuzilma

```
app/
  main.py            FastAPI ilova, sessiya (savatcha cookie'da)
  config.py          sozlamalar (.env)
  models.py          SQLAlchemy modellar — CLAUDE.md dagi sxema
  i18n.py, locales/  UZ/RU interfeys matnlari; mahsulot matnlari bazada *_uz/*_ru
  services/
    catalog.py       katalog va tanlash so'rovlari (product_usages orqali)
    cart.py          savatcha
    orders.py        forma tekshiruvi va buyurtma yaratish
    telegram.py      bot xabari, tugmalar, holatni yangilash
  routers/           pages (sahifalar), shop (savatcha/buyurtma), telegram
  admin/             admin panel: auth, routes, products (forma), media (rasmlar)
  templates/         Jinja2 shablonlar
  static/            css/app.css (mobile-first), js/app.js
migrations/          Alembic
scripts/seed.py      namunaviy ma'lumotlar
scripts/create_admin.py  admin yaratish / parolni almashtirish
```

## Telegram bot

1. @BotFather'da bot yarating, tokenni `TELEGRAM_BOT_TOKEN` ga yozing.
2. Botga `/start` yozing va chat ID'ni `TELEGRAM_CHAT_ID` ga qo‘ying.
3. `TELEGRAM_WEBHOOK_SECRET` ga tasodifiy so‘z yozing va webhook'ni ulang (sayt HTTPS'da bo‘lishi kerak):

```bash
curl "https://api.telegram.org/bot$TOKEN/setWebhook" \
  -d url=https://SAYT.uz/telegram/webhook -d secret_token=$SECRET \
  -d 'allowed_updates=["callback_query"]'
```

Yangi buyurtmada bot xabar yuboradi; “Qabul qilish”, “Qo‘ng‘iroq qildim”, “Yetkazildi”,
“Bekor qilish” tugmalari `orders.status` ni yangilaydi va xabarni tahrirlaydi.
Faqat `TELEGRAM_CHAT_ID` chatidan bosilgan tugmalar qabul qilinadi.
