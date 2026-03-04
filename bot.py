"""
Be-The-Best Fitness Studio — Telegram Bot
==========================================

Run:
    python bot.py

Requirements:
    pip install -r requirements.txt

Setup checklist:
    1. Copy .env.example to .env and paste your BOT_TOKEN
    2. Fill in config.json (owner ID, coach IDs, spreadsheet ID)
    3. Place credentials.json (Google service account key) in this folder
    4. Put schedule.pdf and rules.pdf in the files/ folder
"""
import logging
import sys
import asyncio

# Use selector event loop on Windows to avoid "no current event loop" errors
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
    # ensure a loop is available in the main thread
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception:
        pass

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
import sheets
from handlers import (
    handle_start,
    handle_message,
    handle_contact,
    cb_register,
    cb_cancel_registration,
    build_coach_conv_handler,
    build_mark_class_conv_handler,
    cb_toggle_attendance,
    cb_save_attendance,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    # ── Load configuration ──────────────────────────────────────────────────
    try:
        config.load_config()
        logger.info("Configuration loaded OK")
    except (ValueError, FileNotFoundError) as exc:
        logger.critical("Config error: %s", exc)
        sys.exit(1)

    # ── Connect to Google Sheets ────────────────────────────────────────────
    try:
        sheets.init_sheets(config.SPREADSHEET_ID, config.CREDENTIALS_PATH)
        logger.info("Google Sheets connected OK")
    except FileNotFoundError:
        logger.critical(
            "credentials.json not found at %s. "
            "Download your Google service account key and place it there.",
            config.CREDENTIALS_PATH,
        )
        sys.exit(1)
    except Exception as exc:
        logger.critical("Could not connect to Google Sheets: %s", exc)
        sys.exit(1)

    # ── Build application ───────────────────────────────────────────────────
    app = Application.builder().token(config.BOT_TOKEN).build()

    # Conversation handlers (must be registered BEFORE the generic MessageHandler)
    app.add_handler(build_mark_class_conv_handler())
    app.add_handler(build_coach_conv_handler())

    # Commands
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("menu", handle_start))

    # Contact sharing (new user phone)
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(cb_register, pattern=r"^r:"))
    app.add_handler(CallbackQueryHandler(cb_cancel_registration, pattern=r"^cx:"))
    app.add_handler(CallbackQueryHandler(cb_toggle_attendance, pattern=r"^mkat:"))
    app.add_handler(CallbackQueryHandler(cb_save_attendance, pattern=r"^mksave:"))

    # All other text messages (main menu buttons + fallback)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


    # ── Start polling ───────────────────────────────────────────────────────
    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
