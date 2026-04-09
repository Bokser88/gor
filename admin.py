import asyncio
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_ID
import db

router = Router()
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🎟 Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")]
    ])
    await message.answer("👨‍💼 Панель администратора:", reply_markup=kb)

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): return
    total, premium = await db.get_stats()
    await call.message.answer(f"📊 Статистика:\n👥 Всего пользователей: {total}\n💎 Активных премиум: {premium}")
    await call.answer()

@router.callback_query(F.data == "admin_promo")
async def cb_admin_promo(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): return
    await call.message.answer("📝 Отправь промокод в формате:\n`CODE 30 10`\nГде: `КОД` `дни премиума` `макс активаций`")
    await call.answer()

@router.message(lambda m: len(m.text.split()) == 3 and is_admin(m.from_user.id))
async def process_create_promo(message: types.Message):
    code, days_str, uses_str = message.text.split()
    days, uses = int(days_str), int(uses_str)
    if await db.create_promo(code.upper(), days, uses):
        await message.answer(f"✅ Промокод `{code.upper()}` создан! Дней: {days}, Лимит: {uses}")
    else:
        await message.answer("❌ Такой промокод уже существует.")

@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): return
    await call.message.answer("📩 Отправь текст для рассылки всем пользователям.")
    await call.answer()

@router.message(lambda m: m.text and not m.text.startswith("/") and is_admin(m.from_user.id))
async def process_broadcast(message: types.Message):
    users = await db.get_all_users()
    sent, failed = 0, 0
    for uid in users:
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
        except:
            failed += 1
    await message.answer(f"✅ Рассылка завершена:\nОтправлено: {sent}\nОшибок: {failed}")