import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, GIGA_AUTH_KEY, ADMIN_ID
import db
from astro_ai import AstroAI
from payments import create_payment_link, get_payment_status
import admin

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(admin.router)  # Подключаем админ-панель

ai = AstroAI(auth_key=GIGA_AUTH_KEY)

# FSM-состояния для диалогов
class UserState(StatesGroup):
    waiting_partner_sign = State()
    waiting_question = State()

ZODIAC_SIGNS = [
    ("♈ Овен", "Овен"), ("♉ Телец", "Телец"), ("♊ Близнецы", "Близнецы"),
    ("♋ Рак", "Рак"), ("♌ Лев", "Лев"), ("♍ Дева", "Дева"),
    ("♎ Весы", "Весы"), ("♏ Скорпион", "Скорпион"), ("♐ Стрелец", "Стрелец"),
    ("♑ Козерог", "Козерог"), ("♒ Водолей", "Водолей"), ("♓ Рыбы", "Рыбы")
]

PROMPT_FREE = """Ты — астролог. Краткий гороскоп для знака {sign} на {date}.
Структура: 🌟 Настроение | 💼 Работа | 💕 Отношения | ✨ Совет.
80-100 слов, тёплый тон. В конце: «Прогноз носит развлекательный характер ✨»"""

PROMPT_PREMIUM = """Ты — профессиональный астролог. Развёрнутый гороскоп для знака {sign} на {date}.
Структура строго:
🌟 Энергия дня и настроение
💼 Карьера и финансы (конкретные советы)
💕 Любовь и общение (совместимость с окружением)
🌙 Лунный совет и предостережения
✨ Ритуал/действие на удачу
🍀 Числа и цвета дня
120-150 слов, глубокий и практичный. В конце: «Индивидуальный прогноз для подписчика 💎»"""

# Простой кэш в оперативной памяти (сбрасывается при перезапуске бота)
horoscope_cache = {}

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()  # Сбрасываем зависшие состояния
    await db.create_user(message.from_user.id)
    user = await db.get_user(message.from_user.id)
    
    # user[1] — это знак зодиака в вашей БД
    if user and user[1]:
        await message.answer(f"Привет, {message.from_user.full_name}! 🌟\nМеню: /horoscope /week /ask /compatibility /premium")
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=s[0], callback_data=f"zodiac_{s[1]}")] for s in ZODIAC_SIGNS
        ])
        await message.answer("✨ Выбери свой знак зодиака:", reply_markup=kb)

@dp.callback_query(F.data.startswith("zodiac_"))
async def select_zodiac(call: types.CallbackQuery, state: FSMContext):
    sign = call.data.split("_")[1]
    await db.set_zodiac(call.from_user.id, sign)
    await call.message.edit_text(f"✅ Знак {sign} сохранён! Теперь нажимай /horoscope")
    await call.answer()
    await state.clear()

@dp.message(Command("horoscope"))
async def get_horoscope(message: types.Message):
    await db.create_user(message.from_user.id)
    user = await db.get_user(message.from_user.id)
    
    if not user or not user[1]:
        return await message.answer("Сначала выбери знак зодиака через /start")

    is_prem = await db.is_premium(message.from_user.id)
    sign = user[1]
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"{'p' if is_prem else 'f'}_{sign}_{today}"

    if cache_key in horoscope_cache:
        return await message.answer(horoscope_cache[cache_key])

    await message.answer("✨ Звёзды настраиваются... Подожди пару секунд...")
    prompt = PROMPT_PREMIUM.format(sign=sign, date=today) if is_prem else PROMPT_FREE.format(sign=sign, date=today)
    text = await ai.generate(prompt)

    if text:
        horoscope_cache[cache_key] = text
        await message.answer(text)
    else:
        await message.answer("⚠️ Звёзды сегодня молчат. Попробуй позже или напиши /help")

@dp.message(Command("week"))
async def cmd_week(message: types.Message):
    if not await db.is_premium(message.from_user.id):
        return await message.answer("💎 Прогноз на неделю доступен только в Премиуме. /premium")
    
    user = await db.get_user(message.from_user.id)
    if not user or not user[1]: return await message.answer("Сначала выбери знак через /start")
    
    await message.answer("📅 Формирую прогноз на 7 дней...")
    text = await ai.generate(f"Составь краткий прогноз на неделю (Пн-Вс) для знака {user[1]}. Формат: День → Совет. 100 слов.")
    await message.answer(text or "⚠️ Не удалось сгенерировать прогноз.")

@dp.message(Command("compatibility"))
async def cmd_compat(message: types.Message, state: FSMContext):
    if not await db.is_premium(message.from_user.id):
        return await message.answer("💎 Совместимость доступна только в Премиуме. /premium")
    await message.answer("💕 Напиши знак партнёра (например: Лев):")
    await state.set_state(UserState.waiting_partner_sign)

@dp.message(UserState.waiting_partner_sign)
async def process_compat(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or not user[1]:
        return await message.answer("Сначала выбери свой знак через /start")
        
    partner = message.text.strip()
    await message.answer("🔍 Анализирую звёздную совместимость...")
    prompt = f"Совместимость знаков {user[1]} и {partner}. Анализ по 3 сферам: любовь, общение, конфликты. Советы. 90 слов."
    text = await ai.generate(prompt)
    await message.answer(text or "⚠️ Ошибка анализа.")
    await state.clear()

@dp.message(Command("ask"))
async def cmd_ask(message: types.Message, state: FSMContext):
    if not await db.is_premium(message.from_user.id):
        return await message.answer("💎 Функция «Спроси звёзды» доступна только в Премиуме.")
    await message.answer("🔮 Задай свой вопрос астрологу:")
    await state.set_state(UserState.waiting_question)

@dp.message(UserState.waiting_question)
async def process_ask(message: types.Message, state: FSMContext):
    await message.answer("✨ Звёзды думают...")
    text = await ai.generate(f"Ответь на вопрос пользователя в стиле астролога-мудреца: «{message.text}». 60-80 слов.")
    await message.answer(text or "⚠️ Не удалось получить ответ.")
    await state.clear()

@dp.message(Command("promo"))
async def cmd_promo(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Использование: /promo CODE")
    code = parts[1].upper()
    days = await db.use_promo(code, message.from_user.id)
    if days:
        await db.activate_premium(message.from_user.id, days)
        await message.answer(f"🎁 Промокод активирован! +{days} дней Премиума. Наслаждайся звёздами 💎")
    else:
        await message.answer("❌ Промокод не найден или лимит исчерпан.")

@dp.message(Command("premium"))
async def buy_premium(message: types.Message):
    if await db.is_premium(message.from_user.id):
        return await message.answer("💎 У вас уже активен Премиум! ✨")
        
    pid, url = create_payment_link(message.from_user.id)
    if not url: 
        return await message.answer("❌ Ошибка создания платежа. Попробуй позже.")
        
    await db.set_pending_payment(message.from_user.id, pid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить 299₽", url=url)],
        [InlineKeyboardButton(text="✅ Я оплатил, проверь", callback_data=f"check_{pid}")]
    ])
    await message.answer(
        "💎 Премиум без ограничений:\n"
        "• Приоритетная генерация без очереди\n"
        "• Прогноз на неделю\n"
        "• Совместимость с партнёром\n"
        "• Функция «Спроси звёзды»\n"
        "Оплата безопасна через ЮKassa:",
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("check_"))
async def check_pay(call: types.CallbackQuery):
    pid = call.data.split("check_")[1]
    await call.answer("⏳ Проверяю статус платежа...")
    
    status = await asyncio.to_thread(get_payment_status, pid)

    if status == "succeeded":
        await db.activate_premium(call.from_user.id, days=30)
        await call.message.edit_text("🎉 Оплата подтверждена! Премиум активирован на 30 дней ✨")
    elif status == "pending":
        await call.answer("⏳ Платёж ещё обрабатывается банком. Подождите 1-2 минуты и нажмите кнопку снова.", show_alert=True)
    elif status in ["canceled", "expired"]:
        await call.message.edit_text("❌ Платёж отменён или истёк срок. Попробуйте снова через /premium")
    else:
        await call.answer("⚠️ Не удалось проверить статус. Попробуйте позже.", show_alert=True)

async def main():
    await db.init_db()
    logging.info("📦 База данных инициализирована")
    logging.info("🤖 Бот запущен в режиме polling! Нажмите /start")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
