import aiosqlite
import datetime
import logging

DB_PATH = "bot_data.db"
logger = logging.getLogger(__name__)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            zodiac TEXT,
            premium_until TEXT,
            pending_payment_id TEXT
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY,
            discount_days INTEGER,
            max_uses INTEGER,
            used_count INTEGER DEFAULT 0
        )""")
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()

async def create_user(user_id: int):
    if await get_user(user_id): return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def set_zodiac(user_id: int, zodiac: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET zodiac = ? WHERE user_id = ?", (zodiac, user_id))
        await db.commit()

async def set_pending_payment(user_id: int, payment_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET pending_payment_id = ? WHERE user_id = ?", (payment_id, user_id))
        await db.commit()

async def activate_premium(user_id: int, days: int = 30):
    until = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET premium_until = ?, pending_payment_id = NULL WHERE user_id = ?", (until, user_id))
        await db.commit()

async def is_premium(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user or not user[2]: return False
    return datetime.datetime.fromisoformat(user[2]) > datetime.datetime.now()

# 📊 Статистика для админа
async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c1:
            total = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE premium_until > ?", 
                              (datetime.datetime.now().isoformat(),)) as c2:
            premium = (await c2.fetchone())[0]
        return total, premium

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as c:
            return [row[0] for row in await c.fetchall()]

# 🎟️ Промокоды
async def create_promo(code: str, days: int, max_uses: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO promos (code, discount_days, max_uses) VALUES (?, ?, ?)", 
                             (code, days, max_uses))
            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        return False

async def use_promo(code: str, user_id: int) -> int | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT discount_days, max_uses, used_count FROM promos WHERE code = ?", (code,)) as c:
            row = await c.fetchone()
            if row and row[1] > row[2]:
                await db.execute("UPDATE promos SET used_count = used_count + 1 WHERE code = ?", (code,))
                await db.execute("UPDATE users SET pending_payment_id = NULL WHERE user_id = ?", (user_id,))
                await db.commit()
                return row[0]
    return None