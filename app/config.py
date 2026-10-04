from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://yashil:yashil@localhost:5432/yashil_dala"
    secret_key: str = "dev-secret-change-me"
    default_lang: str = "uz"

    # Do'kon ma'lumotlari (hozircha bo'sh joylar — keyin to'ldiriladi)
    shop_name: str = "Yashil Dala"
    shop_phone: str = "+998 [raqam]"
    shop_address: str = "[manzil]"
    shop_license: str = "[raqam]"
    shop_telegram: str = "https://t.me/"
    delivery_price: int = 0

    # Telegram bot: token bo'lmasa xabar yuborilmaydi (faqat log)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_webhook_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
