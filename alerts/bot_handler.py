"""
Bot command handler for XenonPie Telegram bot.

Commands:
  /start            — welcome + help
  /help             — list all commands
  /govtjobs         — latest central govt jobs
  /statejobs        — latest state govt jobs
  /privatejobs      — latest private/corporate jobs
  /internships      — latest internships
  /indiajobs        — all India (any category)
  /wbjobs           — West Bengal jobs
  /upjobs           — Uttar Pradesh jobs
  /bihajobs         — Bihar jobs
  /rajjobs          — Rajasthan jobs
  /mhjobs           — Maharashtra jobs
  /tnajobs          — Tamil Nadu jobs
  /karnajobs        — Karnataka jobs
  /keralajobs       — Kerala jobs
  /mpjobs           — Madhya Pradesh jobs
  /gjjobs           — Gujarat jobs
  /pbjobs           — Punjab jobs
  /hyjobs           — Haryana jobs
  /ukjobs           — Uttarakhand jobs
  /jkjobs           — Jammu & Kashmir jobs
  /railway          — Railway jobs
  /bank             — Banking jobs
  /defence          — Defence / Army / Navy jobs
  /teaching         — Teaching jobs
  /police           — Police jobs
  /aiJobs           — AI / ML engineer jobs
  /devops           — DevOps jobs
  /backend          — Backend engineer jobs
  /fullstack        — Fullstack engineer jobs
  /dataentry        — Data entry jobs
  /remote           — Remote jobs
  /subscribe        — Subscribe to auto-alerts
  /unsubscribe      — Unsubscribe from alerts
  /status           — Bot status
"""

from datetime import date
from loguru import logger
from alerts.telegram import send_telegram_alert
from alerts.formatter import format_alert

# ── in-memory job store (filled by supervisor as jobs come in) ─────────────────
# Structure: list of job dicts, capped at 500 most recent
_recent_jobs: list[dict] = []
MAX_JOBS = 500

# ── subscriber store (in-memory; swap for Redis/DB later) ─────────────────────
_subscribers: set[str] = set()


def register_job(job: dict):
    """Called by supervisor for every processed job — keeps rolling window."""
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

    for job in reversed(_recent_jobs):  # newest first
        # skip expired
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


# ── command router ─────────────────────────────────────────────────────────────

HELP_TEXT = """
🤖 <b>XenonPie Job Bot</b>

<b>🏛 Govt Jobs</b>
/govtjobs — Central Govt
/statejobs — State Govt (all)
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
/privatejobs — All corporate
/aiJobs — AI / ML
/devops — DevOps
/backend — Backend
/fullstack — Fullstack
/dataentry — Data Entry
/remote — Remote jobs
/internships — Internships

<b>⚙️ Settings</b>
/subscribe — Auto-alerts ON
/unsubscribe — Auto-alerts OFF
/status — Bot status
"""

WELCOME_TEXT = """
👋 <b>Welcome to XenonPie!</b>

I send you fresh job alerts from 100+ Indian govt portals and tech job boards.

Type /help to see all commands.
"""


async def handle_command(chat_id: str, text: str):
    """Route a Telegram command to the right handler."""
    cmd = text.strip().split()[0].lower().lstrip("/").split("@")[0]
    logger.info(f"Bot command /{cmd} from {chat_id}")

    # ── meta ──────────────────────────────────────────────────────────────────
    if cmd == "start":
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
        _subscribers.add(chat_id)
        await send_telegram_alert(
            "✅ <b>Subscribed!</b> You'll get auto-alerts for new jobs matching your profile.",
            chat_id=chat_id,
        )

    elif cmd == "unsubscribe":
        _subscribers.discard(chat_id)
        await send_telegram_alert(
            "🔕 <b>Unsubscribed.</b> You won't get auto-alerts. Use /subscribe to re-enable.",
            chat_id=chat_id,
        )

    # ── central govt ──────────────────────────────────────────────────────────
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

    # ── state-wise ────────────────────────────────────────────────────────────
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

    # ── private / tech ────────────────────────────────────────────────────────
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
        jobs = _filter(source_types=["remotive", "weworkremotely", "himalayas", "remoteok"])
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