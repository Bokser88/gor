import uuid
from yookassa import Configuration, Payment
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, PREMIUM_PRICE, BOT_RETURN_URL

# Инициализация SDK
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

def create_payment_link(user_id: int) -> tuple:
    try:
        payment_id = str(uuid.uuid4())
        payment = Payment.create({
            "amount": {"value": str(PREMIUM_PRICE), "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": BOT_RETURN_URL},
            "capture": True,
            "description": f"Премиум Horoscope+ (User: {user_id})"
        }, idempotency_key=payment_id)
        return payment.id, payment.confirmation.confirmation_url
    except Exception as e:
        print("❌ Ошибка создания платежа ЮKassa:", e)
        return None, None

def get_payment_status(payment_id: str) -> str:
    try:
        payment = Payment.find_one(payment_id)
        return payment.status
    except Exception as e:
        print("❌ Ошибка проверки статуса:", e)
        return "error"