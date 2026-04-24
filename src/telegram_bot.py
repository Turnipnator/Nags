"""
Telegram bot for delivering selections and accepting commands.

Follows the standard trading bot Telegram pattern:
- Auto-sends selections at scheduled time
- Commands for on-demand info
- Restricted to authorised chat_id
"""

import logging
from datetime import date

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

# Global reference to app for sending messages from outside handlers
_app: Application = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not _is_authorised(update):
        return
    await update.message.reply_text(
        "🏇 Horse Racing Bot active.\n"
        "Use /help to see available commands."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if not _is_authorised(update):
        return
    await update.message.reply_text(
        "🏇 *Horse Racing Bot Commands*\n\n"
        "/today - Today's selections + NBs\n"
        "/nap - NAP of the day\n"
        "/nb - Next Best pick\n"
        "/run - Run pipeline (all meetings)\n"
        "/run aintree - Run for specific course(s)\n"
        "/focus aintree - Lock scheduled runs to course(s)\n"
        "/focus - Clear focus (all meetings)\n"
        "/results - Latest results & P&L\n"
        "/streak - Win streak & stats\n"
        "/meetings - Today's meetings\n"
        "/status - Bot health check\n"
        "/stop - Pause selections\n"
        "/resume - Resume selections\n",
        parse_mode="Markdown",
    )


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /today - send today's full selections."""
    if not _is_authorised(update):
        return
    # This will be populated by the scheduler when analysis completes
    from src.database import get_todays_selections
    selections = get_todays_selections()
    if not selections:
        await update.message.reply_text("No selections yet today. Analysis runs at 08:00.")
        return
    await update.message.reply_text(selections, parse_mode="Markdown")


async def nap_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /nap - send NAP of the day."""
    if not _is_authorised(update):
        return
    from src.database import get_todays_nap
    nap = get_todays_nap()
    if not nap:
        await update.message.reply_text("No NAP yet today.")
        return
    await update.message.reply_text(nap, parse_mode="Markdown")


async def nb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /nb - send Next Best."""
    if not _is_authorised(update):
        return
    from src.database import get_todays_next_best
    nb = get_todays_next_best()
    if not nb:
        await update.message.reply_text("No Next Best yet today.")
        return
    await update.message.reply_text(nb, parse_mode="Markdown")


async def results_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /results - latest results and P&L."""
    if not _is_authorised(update):
        return
    from src.database import get_latest_results
    results = get_latest_results()
    if not results:
        await update.message.reply_text("No results recorded yet.")
        return
    await update.message.reply_text(results, parse_mode="Markdown")


async def streak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /streak - win stats."""
    if not _is_authorised(update):
        return
    from src.database import get_stats
    stats = get_stats()
    await update.message.reply_text(stats, parse_mode="Markdown")


async def meetings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /meetings - what's on today."""
    if not _is_authorised(update):
        return
    from src.scraper import Scraper
    scraper = Scraper()
    try:
        meetings = scraper.get_todays_meetings()
        if not meetings:
            await update.message.reply_text("No meetings found for today.")
            return
        text = "📋 *Today's Meetings*\n\n"
        for m in meetings:
            text += f"• {m['course']}\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        scraper.close()


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status - bot health."""
    if not _is_authorised(update):
        return
    from src.database import get_bot_status
    status = get_bot_status()
    await update.message.reply_text(
        f"🟢 *Bot Status*\n\n{status}",
        parse_mode="Markdown",
    )


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop - pause selections."""
    if not _is_authorised(update):
        return
    from src.database import set_bot_paused
    set_bot_paused(True)
    await update.message.reply_text("⏸ Bot paused. Use /resume to restart.")


async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /resume - resume selections."""
    if not _is_authorised(update):
        return
    from src.database import set_bot_paused
    set_bot_paused(False)
    await update.message.reply_text("▶️ Bot resumed.")


async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /run [course ...] - force run the pipeline now, optionally for specific courses."""
    if not _is_authorised(update):
        return
    focus_courses = list(context.args) if context.args else None
    msg = update.message or update.effective_message
    if focus_courses:
        label = ", ".join(c.title() for c in focus_courses)
        if msg:
            await msg.reply_text(f"🏇 Running pipeline for {label}...")
    else:
        if msg:
            await msg.reply_text("🏇 Running pipeline (all meetings)...")
    from main import run_daily_pipeline
    await run_daily_pipeline(focus_courses=focus_courses)


async def focus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /focus [course ...] - set or clear course filter for scheduled runs."""
    if not _is_authorised(update):
        return
    from src.database import _set_state, _get_state
    if context.args:
        courses = ",".join(c.strip().lower() for c in context.args)
        _set_state("focus_courses", courses)
        label = ", ".join(c.title() for c in context.args)
        await update.message.reply_text(f"🎯 Focus set: {label}\nScheduled runs will only analyse these courses.\nUse /focus to clear.")
    else:
        _set_state("focus_courses", "")
        current = _get_state("focus_courses")
        await update.message.reply_text("🌐 Focus cleared. Scheduled runs will analyse all meetings.")


def _is_authorised(update: Update) -> bool:
    """Check if message is from authorised chat."""
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        logger.warning(f"Unauthorised access attempt from chat_id: {update.effective_chat.id}")
        return False
    return True


def create_app() -> Application:
    """Create and configure the Telegram bot application."""
    global _app
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("nap", nap_cmd))
    app.add_handler(CommandHandler("nb", nb_cmd))
    app.add_handler(CommandHandler("results", results_cmd))
    app.add_handler(CommandHandler("streak", streak_cmd))
    app.add_handler(CommandHandler("meetings", meetings_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("resume", resume_cmd))
    app.add_handler(CommandHandler("run", run_cmd))
    app.add_handler(CommandHandler("focus", focus_cmd))

    _app = app
    return app


async def send_message(text: str, parse_mode: str = "Markdown"):
    """Send a message to the authorised chat. Called by scheduler."""
    if _app is None:
        logger.error("Telegram app not initialised")
        return
    try:
        await _app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=parse_mode,
        )
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


async def send_selections(selections: dict):
    """Format and send cherry-picked selections to Telegram."""
    if not selections:
        await send_message("⚠️ No selections generated today.")
        return

    from src.analyst import format_selections_telegram
    formatted = format_selections_telegram(selections)

    if len(formatted) > 4000:
        chunks = _split_message(formatted, 4000)
        for chunk in chunks:
            await send_message(chunk)
    else:
        await send_message(formatted)


def _split_message(text: str, max_len: int) -> list[str]:
    """Split a long message at newline boundaries."""
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Find last newline before max_len
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
