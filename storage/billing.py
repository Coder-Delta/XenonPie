from loguru import logger
from storage.db import get_pool
from datetime import datetime, timedelta

PLANS = {
    "free": {
        "price_inr": 0,
        "alerts_per_day": 5,
        "categories_limit": 2,
        "states_limit": 2,
        "label": "Free",
        "emoji": "🆓",
    },
    "basic": {
        "price_inr": 99,
        "alerts_per_day": 20,
        "categories_limit": 5,
        "states_limit": 5,
        "label": "Basic",
        "emoji": "⭐",
    },
    "pro": {
        "price_inr": 299,
        "alerts_per_day": 100,
        "categories_limit": 20,
        "states_limit": 20,
        "label": "Pro",
        "emoji": "🚀",
    },
    "premium": {
        "price_inr": 599,
        "alerts_per_day": 999,
        "categories_limit": 99,
        "states_limit": 99,
        "label": "Premium",
        "emoji": "💎",
    },
}


async def get_user_plan(chat_id: str) -> dict:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT s.plan_name, s.status, s.expires_at
                FROM subscriptions s
                WHERE s.chat_id = $1 AND s.status = 'active'
            """, chat_id)

            if not row:
                return {"plan_name": "free", **PLANS["free"]}

            plan_name = row["plan_name"]
            expires_at = row["expires_at"]

            if expires_at and expires_at < datetime.now():
                return {"plan_name": "free", **PLANS["free"]}

            plan = PLANS.get(plan_name, PLANS["free"])
            return {"plan_name": plan_name, **plan}
    except Exception as e:
        logger.error(f"get_user_plan error: {e}")
        return {"plan_name": "free", **PLANS["free"]}


async def get_alert_count_today(chat_id: str) -> int:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT count FROM alert_usage
                WHERE chat_id = $1 AND date = CURRENT_DATE
            """, chat_id)
            return row["count"] if row else 0
    except Exception as e:
        logger.error(f"get_alert_count_today error: {e}")
        return 0


async def increment_alert_count(chat_id: str) -> int:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO alert_usage (chat_id, date, count)
                VALUES ($1, CURRENT_DATE, 1)
                ON CONFLICT (chat_id, date) DO UPDATE
                SET count = alert_usage.count + 1
                RETURNING count
            """, chat_id)
            return row["count"] if row else 1
    except Exception as e:
        logger.error(f"increment_alert_count error: {e}")
        return 1


async def can_receive_alert(chat_id: str) -> tuple[bool, str]:
    plan = await get_user_plan(chat_id)
    count = await get_alert_count_today(chat_id)
    limit = plan["alerts_per_day"]

    if plan["plan_name"] == "premium" or limit >= 999:
        return True, ""

    if count >= limit:
        return False, (
            f"🚫 Daily limit reached ({count}/{limit} alerts)\n\n"
            f"Your plan: {plan['emoji']} <b>{plan['label']}</b>\n\n"
            f"Upgrade to get more alerts:\n"
            f"⭐ Basic — ₹99/mo — 20 alerts/day\n"
            f"🚀 Pro — ₹299/mo — 100 alerts/day\n"
            f"💎 Premium — ₹599/mo — Unlimited\n\n"
            f"Use /upgrade to see all plans."
        )
    return True, ""


async def activate_plan(chat_id: str, plan_name: str, payment_id: str = None, months: int = 1) -> bool:
    if plan_name not in PLANS:
        return False
    try:
        pool = await get_pool()
        expires_at = datetime.now() + timedelta(days=30 * months)
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO subscriptions (chat_id, plan_name, status, expires_at, payment_id, amount_paid)
                VALUES ($1, $2, 'active', $3, $4, $5)
                ON CONFLICT (chat_id) DO UPDATE SET
                    plan_name = EXCLUDED.plan_name,
                    status = 'active',
                    expires_at = EXCLUDED.expires_at,
                    payment_id = EXCLUDED.payment_id,
                    amount_paid = EXCLUDED.amount_paid,
                    started_at = NOW()
            """, chat_id, plan_name, expires_at, payment_id,
                PLANS[plan_name]["price_inr"] * months)
        logger.info(f"Plan activated: {chat_id} → {plan_name} until {expires_at}")
        return True
    except Exception as e:
        logger.error(f"activate_plan error: {e}")
        return False


async def get_all_subscribed_users() -> list[dict]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT u.chat_id, u.categories, u.states, u.education_level,
                       COALESCE(s.plan_name, 'free') as plan_name
                FROM users u
                LEFT JOIN subscriptions s ON u.chat_id = s.chat_id AND s.status = 'active'
                WHERE u.subscribed = TRUE
            """)
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_all_subscribed_users error: {e}")
        return []
