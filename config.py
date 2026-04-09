import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
GIGA_AUTH_KEY = os.getenv("GIGA_AUTH_KEY")
BOT_RETURN_URL = os.getenv("BOT_RETURN_URL", "https://t.me/LunaCompass_bot")
PREMIUM_PRICE = 299.00