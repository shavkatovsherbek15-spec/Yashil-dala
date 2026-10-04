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
uvicorn app.main:app --reload    # http://127.0.0.1:8000
```

Hammasini Docker'da: `docker compose up --build`, keyin
`docker compose exec web python -m scripts.seed`.

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
  templates/         Jinja2 shablonlar
  static/            css/app.css (mobile-first), js/app.js
migrations/          Alembic
scripts/seed.py      namunaviy ma'lumotlar
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
