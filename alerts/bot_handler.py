"""
Bot command handler for XenonPie Telegram bot.
"""

from datetime import date
from loguru import logger
from alerts.telegram import send_telegram_alert
from alerts.formatter import format_alert
from storage.db import save_user, get_user, update_user_prefs

# ── in-memory job store ────────────────────────────────────────────────────────
_recent_jobs: list[dict] = []
MAX_JOBS = 500
_subscribers: set[str] = set()


def register_job(job: dict):
    global _recent_jobs
    _recent_jobs.append(job)
    if len(_recent_jobs) > MAX_JOBS:
        _recent_jobs = _recent_jobs[-MAX_JOBS:]


def get_subscribers() -> set[str]:
    return _subscribers


# ── filter helpers ─────────────────────────────────────────────────────────────

def _filter(
    category_tags: list[str] | None = None,
    states: list[str] | None = None,
    source_types: list[str] | None = None,
    limit: int = 5,
) -> list[dict]:
    results = []
    today = date.today()

    for job in reversed(_recent_jobs):
        ld = job.get("last_date")
        if ld and ld != "N/A":
            try:
                if date.fromisoformat(ld) < today:
                    continue
            except Exception:
                pass

        matched = True

        if category_tags:
            tag = job.get("category_tag", "")
            if not any(t in tag for t in category_tags):
                matched = False

        if states and matched:
            loc = (job.get("location") or "").lower().replace(" ", "_")
            state_match = loc == "all_india" or any(s in loc for s in states)
            if not state_match:
                matched = False

        if source_types and matched:
            feed = (job.get("source_feed") or "").lower()
            if not any(st in feed for st in source_types):
                matched = False

        if matched:
            results.append(job)
            if len(results) >= limit:
                break

    return results


def _format_jobs(jobs: list[dict], header: str) -> str:
    if not jobs:
        return f"{header}\n\n<i>No recent jobs found. Check back soon!</i>"
    parts = [header]
    for job in jobs:
        parts.append("\n" + format_alert(job))
        parts.append("─" * 30)
    return "\n".join(parts)


# ── texts ──────────────────────────────────────────────────────────────────────

HELP_TEXT = """
🤖 <b>XenonPie Job Bot</b>

<b>🏛 Govt Jobs</b>
/govtjobs — Central Govt
/statejobs — State Govt
/railway — Railway
/bank — Banking
/defence — Defence
/teaching — Teaching
/police — Police

<b>🗺 State Jobs</b>
/wbjobs — West Bengal
/upjobs — Uttar Pradesh
/bihajobs — Bihar
/rajjobs — Rajasthan
/mhjobs — Maharashtra
/tnajobs — Tamil Nadu
/karnajobs — Karnataka
/keralajobs — Kerala
/mpjobs — Madhya Pradesh
/gjjobs — Gujarat
/pbjobs — Punjab
/hyjobs — Haryana
/ukjobs — Uttarakhand
/jkjobs — J&K
/indiajobs — All India

<b>💼 Private / Tech</b>
/privatejobs — Corporate
/aijobs — AI / ML
/devops — DevOps
/backend — Backend
/fullstack — Fullstack
/dataentry — Data Entry
/remote — Remote
/internships — Internships

<b>👤 Your Profile</b>
/myprofile — View settings
/setstate <state> — Add state filter
/setcategory <cat> — Add category
/seteducation <level> — Set education
/resetprofile — Reset defaults
/subscribe — Auto-alerts ON
/unsubscribe — Auto-alerts OFF
/status — Bot status
"""

WELCOME_TEXT = """
👋 <b>Welcome to XenonPie!</b>

I send fresh job alerts from 100+ Indian govt portals.

<b>Get started:</b>
1️⃣ /setstate west_bengal
2️⃣ /setcategory bank
3️⃣ /seteducation graduate
4️⃣ /subscribe

Type /help to see all commands.
"""


# ── command router ─────────────────────────────────────────────────────────────

async def handle_command(chat_id: str, text: str):
    cmd = text.strip().split()[0].lower().lstrip("/").split("@")[0]
    args = text.strip().split()[1:]
    logger.info(f"Bot command /{cmd} from {chat_id}")

    # ── meta ──────────────────────────────────────────────────────────────────
    if cmd == "start":
        try:
            await save_user(chat_id=chat_id, name="user")
            # do NOT auto-subscribe — user must explicitly set preferences and send /subscribe
        except Exception as e:
            logger.error(f"Save user error: {e}")
        await send_telegram_alert(WELCOME_TEXT, chat_id=chat_id)

    elif cmd in ("help", "commands"):
        await send_telegram_alert(HELP_TEXT, chat_id=chat_id)

    elif cmd == "status":
        total = len(_recent_jobs)
        subs = len(_subscribers)
        subscribed = "✅ Subscribed" if chat_id in _subscribers else "❌ Not subscribed"
        msg = (
            f"⚙️ <b>XenonPie Status</b>\n\n"
            f"📦 Jobs in memory: {total}\n"
            f"👥 Subscribers: {subs}\n"
            f"🔔 Your status: {subscribed}"
        )
        await send_telegram_alert(msg, chat_id=chat_id)

    elif cmd == "subscribe":
        try:
            user = await get_user(chat_id) or {}
            cats = user.get("categories") or []
            states = user.get("states") or ["all_india"]
            if not cats and states == ["all_india"]:
                await send_telegram_alert(
                    "⚠️ Please set your preferences first:\n\n"
                    "/setstate west_bengal\n"
                    "/setcategory bank\n"
                    "/seteducation graduate\n\n"
                    "Then send /subscribe again.",
                    chat_id=chat_id
                )
                return
            _subscribers.add(chat_id)
            await update_user_prefs(chat_id, {
                "categories": cats,
                "states": states,
                "education_level": user.get("education_level") or "graduate",
                "subscribed": True,
            })
        except Exception as e:
            logger.error(f"Subscribe DB error: {e}")
        await send_telegram_alert(
            "✅ <b>Subscribed!</b> You'll get auto-alerts for new matching jobs.",
            chat_id=chat_id,
        )

    elif cmd == "unsubscribe":
        _subscribers.discard(chat_id)
        try:
            user = await get_user(chat_id) or {}
            await update_user_prefs(chat_id, {
                "categories": user.get("categories") or [],
                "states": user.get("states") or ["all_india"],
                "education_level": user.get("education_level") or "graduate",
                "subscribed": False,
            })
        except Exception as e:
            logger.error(f"Unsubscribe DB error: {e}")
        await send_telegram_alert(
            "🔕 <b>Unsubscribed.</b> Use /subscribe to re-enable.",
            chat_id=chat_id,
        )

    # ── profile management ─────────────────────────────────────────────────────
    elif cmd == "myprofile":
        try:
            user = await get_user(chat_id)
            if not user:
                await send_telegram_alert(
                    "No profile found. Send /start first.",
                    chat_id=chat_id
                )
                return
            cats = ", ".join(user.get("categories") or []) or "all"
            states = ", ".join(user.get("states") or ["all_india"])
            edu = user.get("education_level") or "graduate"
            sub = "✅ ON" if user.get("subscribed") else "❌ OFF"
            msg = (
                f"👤 <b>Your Profile</b>\n\n"
                f"📂 Categories: <b>{cats}</b>\n"
                f"🗺 States: <b>{states}</b>\n"
                f"🎓 Education: <b>{edu}</b>\n"
                f"🔔 Auto-alerts: {sub}\n\n"
                f"Use /setcategory, /setstate, /seteducation to update."
            )
            await send_telegram_alert(msg, chat_id=chat_id)
        except Exception as e:
            logger.error(f"myprofile error: {e}")
            await send_telegram_alert("Error loading profile.", chat_id=chat_id)

    elif cmd == "setstate":
        if not args:
            await send_telegram_alert(
                "Usage: /setstate <state>\n\nExamples:\n"
                "/setstate west_bengal\n"
                "/setstate uttar_pradesh\n"
                "/setstate all_india",
                chat_id=chat_id
            )
            return
        state = "_".join(args).lower().replace(" ", "_")
        try:
            user = await get_user(chat_id) or {}
            states = list(user.get("states") or ["all_india"])
            if state not in states:
                states.append(state)
            await update_user_prefs(chat_id, {
                "states": states,
                "categories": user.get("categories") or [],
                "education_level": user.get("education_level") or "graduate",
                "subscribed": user.get("subscribed", True),
            })
            await send_telegram_alert(
                f"✅ State added: <b>{state}</b>\n\nYour states: {', '.join(states)}\n\nUse /myprofile to see all settings.",
                chat_id=chat_id
            )
        except Exception as e:
            logger.error(f"setstate error: {e}")
            await send_telegram_alert("Error updating state.", chat_id=chat_id)

    elif cmd == "setcategory":
        if not args:
            await send_telegram_alert(
                "Usage: /setcategory <category>\n\nOptions:\n"
                "central_govt, state_govt, bank, railway\n"
                "defence, psu, police, teaching, other",
                chat_id=chat_id
            )
            return
        cat = args[0].lower()
        try:
            user = await get_user(chat_id) or {}
            cats = list(user.get("categories") or [])
            if cat not in cats:
                cats.append(cat)
            await update_user_prefs(chat_id, {
                "categories": cats,
                "states": user.get("states") or ["all_india"],
                "education_level": user.get("education_level") or "graduate",
                "subscribed": user.get("subscribed", True),
            })
            await send_telegram_alert(
                f"✅ Category added: <b>{cat}</b>\n\nYour categories: {', '.join(cats)}\n\nUse /myprofile to see all settings.",
                chat_id=chat_id
            )
        except Exception as e:
            logger.error(f"setcategory error: {e}")
            await send_telegram_alert("Error updating category.", chat_id=chat_id)

    elif cmd == "seteducation":
        if not args:
            await send_telegram_alert(
                "Usage: /seteducation <level>\n\nOptions:\n"
                "10th, 12th, diploma, graduate, postgraduate, phd",
                chat_id=chat_id
            )
            return
        edu = args[0].lower()
        valid = ["10th", "12th", "diploma", "graduate", "postgraduate", "phd"]
        if edu not in valid:
            await send_telegram_alert(
                f"Invalid level. Choose from: {', '.join(valid)}",
                chat_id=chat_id
            )
            return
        try:
            user = await get_user(chat_id) or {}
            await update_user_prefs(chat_id, {
                "categories": user.get("categories") or [],
                "states": user.get("states") or ["all_india"],
                "education_level": edu,
                "subscribed": user.get("subscribed", True),
            })
            await send_telegram_alert(
                f"✅ Education level set to: <b>{edu}</b>",
                chat_id=chat_id
            )
        except Exception as e:
            logger.error(f"seteducation error: {e}")
            await send_telegram_alert("Error updating education.", chat_id=chat_id)

    elif cmd == "resetprofile":
        try:
            await update_user_prefs(chat_id, {
                "categories": [],
                "states": ["all_india"],
                "education_level": "graduate",
                "subscribed": True,
            })
            _subscribers.add(chat_id)
            await send_telegram_alert(
                "✅ Profile reset to defaults.\n\nYou'll receive all India jobs at graduate level.",
                chat_id=chat_id
            )
        except Exception as e:
            logger.error(f"resetprofile error: {e}")
            await send_telegram_alert("Error resetting profile.", chat_id=chat_id)

    # ── govt jobs ──────────────────────────────────────────────────────────────
    elif cmd == "govtjobs":
        jobs = _filter(category_tags=["central_govt"])
        await send_telegram_alert(
            _format_jobs(jobs, "🏛 <b>Latest Central Govt Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "statejobs":
        jobs = _filter(category_tags=["state_govt", "psc", "panchayat"])
        await send_telegram_alert(
            _format_jobs(jobs, "🏢 <b>Latest State Govt Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "railway":
        jobs = _filter(category_tags=["railway"])
        await send_telegram_alert(
            _format_jobs(jobs, "🚂 <b>Railway Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "bank":
        jobs = _filter(category_tags=["bank"])
        await send_telegram_alert(
            _format_jobs(jobs, "🏦 <b>Banking Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "defence":
        jobs = _filter(category_tags=["defence"])
        await send_telegram_alert(
            _format_jobs(jobs, "🪖 <b>Defence Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "teaching":
        jobs = _filter(category_tags=["teaching"])
        await send_telegram_alert(
            _format_jobs(jobs, "📚 <b>Teaching Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "police":
        jobs = _filter(category_tags=["police"])
        await send_telegram_alert(
            _format_jobs(jobs, "👮 <b>Police Jobs</b>"), chat_id=chat_id
        )

    # ── state-wise ─────────────────────────────────────────────────────────────
    elif cmd == "indiajobs":
        jobs = _filter(states=["all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🇮🇳 <b>All India Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "wbjobs":
        jobs = _filter(states=["west_bengal", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>West Bengal Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "upjobs":
        jobs = _filter(states=["uttar_pradesh", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Uttar Pradesh Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "bihajobs":
        jobs = _filter(states=["bihar", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Bihar Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "rajjobs":
        jobs = _filter(states=["rajasthan", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Rajasthan Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "mhjobs":
        jobs = _filter(states=["maharashtra", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Maharashtra Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "tnajobs":
        jobs = _filter(states=["tamil_nadu", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Tamil Nadu Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "karnajobs":
        jobs = _filter(states=["karnataka", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Karnataka Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "keralajobs":
        jobs = _filter(states=["kerala", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Kerala Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "mpjobs":
        jobs = _filter(states=["madhya_pradesh", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Madhya Pradesh Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "gjjobs":
        jobs = _filter(states=["gujarat", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Gujarat Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "pbjobs":
        jobs = _filter(states=["punjab", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Punjab Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "hyjobs":
        jobs = _filter(states=["haryana", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Haryana Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "ukjobs":
        jobs = _filter(states=["uttarakhand", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>Uttarakhand Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "jkjobs":
        jobs = _filter(states=["jammu_kashmir", "all_india"])
        await send_telegram_alert(
            _format_jobs(jobs, "🗺 <b>J&K Jobs</b>"), chat_id=chat_id
        )

    # ── private / tech ─────────────────────────────────────────────────────────
    elif cmd == "privatejobs":
        jobs = _filter(category_tags=["private", "tech", "corporate", "startup"])
        await send_telegram_alert(
            _format_jobs(jobs, "💼 <b>Private / Corporate Jobs</b>"), chat_id=chat_id
        )

    elif cmd in ("aijobs", "ai"):
        jobs = _filter(category_tags=["ai", "ml", "machine_learning"])
        await send_telegram_alert(
            _format_jobs(jobs, "🤖 <b>AI / ML Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "devops":
        jobs = _filter(category_tags=["devops", "sysadmin", "cloud"])
        await send_telegram_alert(
            _format_jobs(jobs, "⚙️ <b>DevOps Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "backend":
        jobs = _filter(category_tags=["backend", "backend_dev"])
        await send_telegram_alert(
            _format_jobs(jobs, "🖥 <b>Backend Engineer Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "fullstack":
        jobs = _filter(category_tags=["fullstack", "full_stack"])
        await send_telegram_alert(
            _format_jobs(jobs, "🔗 <b>Fullstack Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "dataentry":
        jobs = _filter(category_tags=["data_entry", "bpo", "data"])
        await send_telegram_alert(
            _format_jobs(jobs, "📋 <b>Data Entry Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "remote":
        jobs = _filter(source_types=["remotive", "weworkremotely", "himalayas"])
        await send_telegram_alert(
            _format_jobs(jobs, "🌐 <b>Remote Jobs</b>"), chat_id=chat_id
        )

    elif cmd == "internships":
        jobs = _filter(category_tags=["internship"])
        await send_telegram_alert(
            _format_jobs(jobs, "🎓 <b>Internships</b>"), chat_id=chat_id
        )

    else:
        await send_telegram_alert(
            f"❓ Unknown command <code>/{cmd}</code>\n\nType /help for all commands.",
            chat_id=chat_id,
        )