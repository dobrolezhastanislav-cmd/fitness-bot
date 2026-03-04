"""
Reminder scheduler (UC-5).

Runs every minute via PTB's JobQueue.
Sends a reminder to all clients registered for a class that starts in ~75 minutes.
Tracks sent reminders in sent_reminders.json to avoid duplicates after bot restart.
"""
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from telegram.ext import ContextTypes

import config
import sheets


# helper copied from handlers for consistent date/time formatting

def _short_datetime(date_str: str, time_str: str) -> str:
    d = date_str or ""
    if d and "." in d:
        parts = d.split('.')
        if len(parts) >= 2:
            d = f"{parts[0]}.{parts[1]}"
    t = time_str or ""
    if len(t) >= 5:
        t = t[:5]
    return f"{d} - {t}" if d or t else ""

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
SENT_FILE = BASE_DIR / "sent_reminders.json"

REMINDER_MINUTES_BEFORE = 75  # UC-5.1: 1 hour and 15 minutes
CHECK_WINDOW_MINUTES = 2       # ±2 min window so we don't miss with scheduling drift


def _load_sent() -> set:
    if SENT_FILE.exists():
        try:
            with open(SENT_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_sent(sent: set) -> None:
    # Keep only entries from the last 7 days to avoid unbounded growth
    try:
        with open(SENT_FILE, "w", encoding="utf-8") as f:
            json.dump(list(sent), f)
    except Exception as exc:
        logger.error("Could not save sent_reminders.json: %s", exc)


def _reminder_key(class_id, class_date: str) -> str:
    return f"{class_id}:{class_date}"


async def send_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Job callback — runs every minute.
    Checks for classes starting in ~75 minutes and sends reminders.
    """
    try:
        tz = pytz.timezone(config.TIMEZONE)
    except Exception:
        tz = pytz.utc

    now = datetime.now(tz).replace(tzinfo=None)  # naive local time
    target_start = now + timedelta(minutes=REMINDER_MINUTES_BEFORE - CHECK_WINDOW_MINUTES)
    target_end = now + timedelta(minutes=REMINDER_MINUTES_BEFORE + CHECK_WINDOW_MINUTES)

    try:
        classes = sheets.get_upcoming_classes(
            within_minutes=REMINDER_MINUTES_BEFORE,
            from_now=now,
        )
    except Exception as exc:
        logger.error("Reminder: error fetching classes: %s", exc)
        return

    if not classes:
        return

    sent_set = _load_sent()
    changed = False

    for cls in classes:
        key = _reminder_key(cls.get("ClassID", ""), str(cls.get("ClassDate", "")))
        if key in sent_set:
            continue  # already sent

        # Fetch registered clients for this class
        try:
            clients = sheets.get_attendees_for_class(cls["ClassID"])
        except Exception as exc:
            logger.error("Reminder: error fetching attendees: %s", exc)
            continue

        class_label = (
            f"{cls.get('ClassName', '')} "
            f"({_short_datetime(cls.get('ClassDate', ''), cls.get('ClassStart', ''))})"
        )
        message = (
            f"⏰ Нагадування: за годину в тебе заняття у Be-The-Best Fitness Studio!\n\n"
            f"🏋️ {class_label}\n\n"
            f"Дай знати, будь ласка, якщо змінилися плани. 🙏"
        )

        any_sent = False
        for client in clients:
            tg_id = str(client.get("UserTelegramID", "")).strip()
            if not tg_id:
                continue
            try:
                await context.bot.send_message(chat_id=int(tg_id), text=message)
                any_sent = True
                logger.info("Reminder sent to %s for class %s", tg_id, key)
            except Exception as exc:
                logger.warning("Could not send reminder to %s: %s", tg_id, exc)

        if any_sent:
            sent_set.add(key)
            changed = True

    if changed:
        _save_sent(sent_set)


def setup_reminders(application) -> None:
    """Register the reminder job with PTB's JobQueue."""
    if application.job_queue is None:
        logger.warning("JobQueue is not available — reminders disabled. "
                       "Install python-telegram-bot[job-queue].")
        return
    application.job_queue.run_repeating(
        send_reminders,
        interval=60,   # every 60 seconds
        first=10,      # start 10 seconds after bot startup
        name="reminders",
    )
    logger.info("Reminder job scheduled (every 60 s, %d min before class)", REMINDER_MINUTES_BEFORE)
