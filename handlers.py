"""
All Telegram bot handlers.

Client buttons (ReplyKeyboard):
  Записатися на заняття | Скасувати запис
  Проглянути інформацію про себе | Розклад
  Правила студії | Instagram

Coach buttons (extra):
  Розіслати повідомлення

Conversation states (coach broadcast flow):
  COACH_SELECT_TARGET → COACH_SELECT_CLASS or COACH_TYPE_MSG → COACH_CONFIRM
"""
import logging
import os
import re
from typing import Optional

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)
from telegram.constants import ParseMode

import config
import sheets

logger = logging.getLogger(__name__)

# ── Button labels (Ukrainian) ───────────────────────────────────────────────


# Date/time formatting helpers ------------------------------------------------

def _short_datetime(date_str: str, time_str: str) -> str:
    """Return date without year and time without seconds ("DD.MM - HH:MM")."""
    d = date_str or ""
    if d and "." in d:
        parts = d.split('.')
        if len(parts) >= 2:
            d = f"{parts[0]}.{parts[1]}"
    t = time_str or ""
    if len(t) >= 5:
        t = t[:5]
    return f"{d} - {t}" if d or t else ""
BTN_REGISTER = "📝 Записатися на заняття"
BTN_CANCEL = "❌ Скасувати запис"
BTN_MY_INFO = "👱‍♀️ Мій профіль"
BTN_SCHEDULE = "📅 Розклад"
BTN_RULES = "📋 Правила студії"
BTN_INSTAGRAM = "📸 Instagram"
BTN_BROADCAST = "📢 Розіслати повідомлення"
BTN_MARK_CLASS = "✅ Відмітити заняття"
BTN_CLASS_ATTENDEES = "👯‍♀️ Список учасників"

CLIENT_KEYBOARD = ReplyKeyboardMarkup(
    [
        [BTN_REGISTER, BTN_CANCEL],
        [BTN_MY_INFO, BTN_SCHEDULE],
        [BTN_RULES, BTN_INSTAGRAM],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

COACH_KEYBOARD = ReplyKeyboardMarkup(
    [
        [BTN_BROADCAST],
        [BTN_MARK_CLASS],
        [BTN_CLASS_ATTENDEES],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

# ConversationHandler states — broadcast
COACH_SELECT_TARGET, COACH_SELECT_CLASS, COACH_TYPE_MSG, COACH_CONFIRM = range(4)

# ConversationHandler states — mark class
MARK_SELECT_CLASS, MARK_RAN_OR_NOT, MARK_CANCEL_REASON = range(10, 13)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    return COACH_KEYBOARD if config.is_coach(user_id) else CLIENT_KEYBOARD


def _inline(*buttons: tuple) -> InlineKeyboardMarkup:
    """Build inline keyboard from list of (label, callback_data) tuples."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=cb)] for label, cb in buttons])


def _class_label(cls: dict) -> str:
    # used for listing open classes; shorten date/time for clarity
    name = cls.get('ClassName', '—')
    dt = _short_datetime(cls.get('ClassDate', ''), cls.get('ClassStart', ''))
    return f"{name} ({dt})" if dt else name


async def _send_file_or_text(update: Update, filepath: str, fallback: str, parse_mode=None) -> None:
    if filepath and os.path.isfile(filepath):
        ext = os.path.splitext(filepath)[1].lower()
        with open(filepath, "rb") as f:
            if ext in (".jpg", ".jpeg", ".png"):
                await update.message.reply_photo(f)
            else:
                await update.message.reply_document(f)
    else:
        await update.message.reply_text(fallback, parse_mode=parse_mode)


# ── TEMP: Coach notifications on client registration/cancellation ────────────
# To remove: delete this function + the 2 lines that call it in cb_register and cb_cancel_registration

async def _notify_coaches(context, client: dict, cls: dict, action: str) -> None:
    client_name = f"{client.get('FirstName', '')} {client.get('LastName', '')}".strip() or "Клієнт"
    class_label = f"{cls.get('ClassName', '—')} ({_short_datetime(cls.get('ClassDate', ''), cls.get('ClassStart', ''))})" if cls else "—"
    text = f"📝 {client_name} записалася на {class_label}" if action == "register" else f"❌ {client_name} скасувала запис на {class_label}"
    for coach_id in config.COACH_TG_IDS:
        try:
            await context.bot.send_message(chat_id=coach_id, text=text)
        except Exception as exc:
            logger.warning("Could not notify coach %s: %s", coach_id, exc)

# ── END TEMP ──────────────────────────────────────────────────────────────────


# ── First contact (UC-1) ─────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for every text message that isn't caught by other handlers."""
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()

    # ── Coach-only: delegate to coach_start if not in a conversation ────────
    if text == BTN_BROADCAST and config.is_coach(user_id):
        return  # handled by ConversationHandler entry_point

    # ── Check if client ─────────────────────────────────────────────────────
    client = sheets.get_client_by_telegram_id(user_id)
    is_coach_user = config.is_coach(user_id)

    if not client and not is_coach_user:
        # If user typed a phone-like text, treat it as a manual contact share
        text = text or ""
        if text and any(ch.isdigit() for ch in text):
            # naive check: contains digits and isn't a command
            # forward to contact handler by fabricating a contact object
            class DummyContact:
                def __init__(self, number):
                    self.phone_number = number

            update.message.contact = DummyContact(text)
            await handle_contact(update, context)
            return
        await _handle_unknown_user(update, context)
        return

    # ── Route to client features ────────────────────────────────────────────
    if text == BTN_REGISTER:
        await _show_open_classes(update, context)
    elif text == BTN_CANCEL:
        await _show_planned_registrations(update, context, client)
    elif text == BTN_MY_INFO:
        await _show_my_info(update, context, client)
    elif text == BTN_SCHEDULE:
        await _send_file_or_text(
            update, config.SCHEDULE_FILE,
            f'Розклад тимчасово недоступний. Завітай на наш <a href="{config.INSTAGRAM_URL}">Instagram</a>',
            parse_mode=ParseMode.HTML,
        )
    elif text == BTN_RULES:
        await _send_file_or_text(
            update, config.RULES_FILE,
            f'Правила студії тимчасово недоступні. Завітай на наш <a href="{config.INSTAGRAM_URL}">Instagram</a>',
            parse_mode=ParseMode.HTML,
        )
    elif text == BTN_INSTAGRAM:
        await update.message.reply_text(
            f"Наш Instagram: {config.INSTAGRAM_URL}",
            disable_web_page_preview=False,
        )
    elif text == BTN_CLASS_ATTENDEES:
        await _show_class_attendees_list(update, context)
    else:
        # Any unrecognised message → show menu
        name = client.get("FirstName", "") if client else "Тренер"
        await update.message.reply_text(
            f"Привіт, {name}! Я би з радістю поспілкувався, але мене того не навчили. "
            f"Я розумію тільки команди з кнопок. Також, май на увазі, нашу з тобою переписку Оля не бачить. "
            f"Тому, якщо тобі щось треба - пиши їй напряму. Обери дію 👇",
            reply_markup=_main_keyboard(user_id),
        )


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start command — same as first message."""
    await handle_message(update, context)


async def _handle_unknown_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User is not in 0_Clients and not a coach."""
    user_id = update.effective_user.id if update.effective_user else None
    logger.info("prompting unknown user for contact: %s", user_id)
    contact_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Поділитися номером телефону", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        "Добрий день! Схоже, Ви не являєтеся відвідувачем нашої студії або у нас не зафіксований Ваш контакт. "
        "Поділіться своїм номером телефону і ми все владнаємо. 🙏\n\n"
        "Якщо кнопка не з'являється (наприклад, у веб‑версії Telegram), "
        "просто надішліть свій номер у відповіді.",
        reply_markup=contact_keyboard,
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle phone number shared by a non-client user (UC-1)."""
    user = update.effective_user
    contact = update.message.contact
    phone = contact.phone_number if contact else "невідомо"

    await update.message.reply_text(
        "Дякую. Чекате на зворотній зв'язок від Олі 😊",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Поділитися номером телефону", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    if config.OWNER_TG_ID:
        try:
            await context.bot.send_message(
                chat_id=config.OWNER_TG_ID,
                text=(
                    f"🆕 Новий потенційний клієнт!\n"
                    f"Моб: {phone}\n"
                    f"TelegramID: {user.id}\n"
                    f"Нік: @{user.username or '—'}\n"
                    f"Ім'я: {user.full_name}"
                ),
            )
        except Exception as exc:
            logger.error("Could not notify owner: %s", exc)


# ── UC-2: Register for a class ───────────────────────────────────────────────

async def _show_open_classes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        classes = sheets.get_open_classes()
    except Exception as exc:
        logger.error("Sheets error: %s", exc)
        await update.message.reply_text("⚠️ Помилка підключення до Google Sheets. Спробуй пізніше.")
        return

    if not classes:
        await update.message.reply_text("На сьогодні немає занять, доступних для запису. 😔")
        return

    buttons = [
        [InlineKeyboardButton(_class_label(c), callback_data=f"r:{c['ClassID']}")]
        for c in classes
    ]
    await update.message.reply_text(
        "Обери заняття для запису:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def cb_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: user selected a class to register for (callback_data = 'r:<class_id>')."""
    query = update.callback_query

    # logging for diagnostics
    user_id = getattr(query.from_user, 'id', None) if query else None
    class_id = None
    if query and query.data:
        class_id = query.data.split(":", 1)[1]
    logger.info("cb_register invoked user=%s class=%s", user_id, class_id)

    try:
        if query:
            await query.answer()

        client = sheets.get_client_by_telegram_id(user_id)
        if not client:
            text = "⚠️ Інформацію про тебе не знайдено. Звернися до Олі"
            if query:
                await query.edit_message_text(text)
            else:
                await context.bot.send_message(chat_id=user_id, text=text)
            return

        cls = sheets.get_class_by_id(class_id)
        if not cls:
            text = "Заняття не знайдено."
            if query:
                await query.edit_message_text(text)
            else:
                await context.bot.send_message(chat_id=user_id, text=text)
            return

        ok, err = sheets.register_client(client, cls)
        if ok:
            formatted = _short_datetime(cls.get('ClassDate'), cls.get('ClassStart'))
            await query.edit_message_text(
                f"✅ Ти успішно записалася на заняття:\n"
                f"*{cls.get('ClassName')}* ({formatted})",
                parse_mode=ParseMode.MARKDOWN,
            )
            await _notify_coaches(context, client, cls, "register")  # TEMP
        elif err == "already_registered":
            await query.edit_message_text("Ти вже йдеш на це заняття. 😊")
        elif err == "closed":
            await query.edit_message_text(
                "Нажаль, запис на це заняття закрився. Чекаємо тебе на наступних заняттях. 😊"
            )
        elif err == "full":
            await query.edit_message_text(
                "Нажаль, на це заняття не залишилося вільних місць. Обери інше заняття. 😔"
            )
        else:
            await query.edit_message_text("⚠️ Помилка запису. Спробуй ще раз або звернися до Олі")

    except Exception as exc:
        logger.exception("Error in cb_register (user=%s class=%s): %s", user_id, class_id, exc)
        # attempt to notify the user at least once
        try:
            if query and query.message:
                await query.message.reply_text("⚠️ Сталася помилка, спробуй ще раз.")
            elif user_id:
                await context.bot.send_message(chat_id=user_id, text="⚠️ Сталася помилка, спробуй ще раз.")
        except Exception:
            pass


# ── UC-3: Cancel registration ─────────────────────────────────────────────────

async def _show_planned_registrations(
    update: Update, context: ContextTypes.DEFAULT_TYPE, client: Optional[dict]
) -> None:
    if not client:
        await update.message.reply_text("⚠️ Ваш профіль не знайдено.")
        return
    try:
        registrations = sheets.get_planned_registrations(client["ClientID"])
    except Exception as exc:
        logger.error("Sheets error: %s", exc)
        await update.message.reply_text("⚠️ Помилка підключення. Спробуй пізніше.")
        return

    if not registrations:
        await update.message.reply_text("Ти не записана на жодне заняття. 😊")
        return

    buttons = [
        [InlineKeyboardButton(
            f"{r.get('ClassName', '—')} ({_short_datetime(r.get('ClassDate',''), r.get('ClassStart',''))})",
            callback_data=f"cx:{r.get('ClassID', '')}",
        )]
        for r in registrations
    ]
    await update.message.reply_text(
        "Обери заняття для скасування запису:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def cb_cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: user selected a registration to cancel (callback_data = 'cx:<class_id>')."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    class_id = query.data.split(":", 1)[1]

    client = sheets.get_client_by_telegram_id(user_id)
    if not client:
        await query.edit_message_text("⚠️ Твій профіль не знайдено. Звернися до Олі")
        return

    cls = sheets.get_class_by_id(class_id)
    cls_label = (
        f"{cls.get('ClassName')} ({_short_datetime(cls.get('ClassDate'), cls.get('ClassStart'))})"
        if cls else f"Заняття #{class_id}"
    )

    ok, err = sheets.cancel_registration(client["ClientID"], class_id)
    if ok:
        await query.edit_message_text(
            f"✅ Твій запис на {cls_label} скасовано. Чекаємо тебе на наступних заняттях! 🙏",
        )
        await _notify_coaches(context, client, cls, "cancel")  # TEMP
    elif err == "not_allowed":
        await query.edit_message_text(
            "Нажаль, скасувати запис на це заняття вже неможливо. 😔 Звернися до Олі, щось придумаєм ;)"
        )
    else:
        await query.edit_message_text("⚠️ Не вдалося скасувати запис. Звернися до Олі")


# ── UC-4: My info ─────────────────────────────────────────────────────────────

async def _show_my_info(
    update: Update, context: ContextTypes.DEFAULT_TYPE, client: Optional[dict]
) -> None:
    if not client:
        await update.message.reply_text("⚠️ Твій профіль не знайдено в базі студії. Звернися до Олі")
        return

    first = client.get("FirstName", "")
    last = client.get("LastName", "")
    valid_through = client.get("ValidThrough", "—")
    paid_left = client.get("ValidPaidAttendances", "—")
    last_visit = client.get("LastVisit", "—")

    # Build the message with client info
    msg = (
        f"👱‍♀️ *Твій профіль*\n\n"
        f"*Клієнт:* {last} {first}\n"
        f"*Абонемент дійсний до:* {valid_through}\n"
        f"*Лишилося занять:* {paid_left}\n"
        f"*Останній візит:* {last_visit}"
    )

    # Add planned registrations if any
    try:
        planned = sheets.get_planned_registrations(client.get("ClientID", ""))
    except Exception as exc:
        logger.error("Sheets error in _show_my_info: %s", exc)
        await update.message.reply_text("⚠️ Помилка підключення. Спробуй пізніше.")
        return
    if planned:
        msg += "\n\n*Заплановані заняття*\n"
        for reg in planned:
            class_name = reg.get("ClassName", "—")
            formatted = _short_datetime(reg.get("ClassDate", ""), reg.get("ClassStart", ""))
            msg += f"• {class_name} ({formatted})\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ── UC-7: Coach mark class as run / not run ──────────────────────────────────

def _build_attendance_keyboard(class_id: str, attendees: list, selected: set) -> InlineKeyboardMarkup:
    """Build inline keyboard for toggling per-attendee presence."""
    buttons = []
    for a in attendees:
        tick = "✅" if a["client_id"] in selected else "☐"
        buttons.append([InlineKeyboardButton(
            f"{tick} {a['name']}",
            callback_data=f"mkat:{class_id}:{a['client_id']}",
        )])
    buttons.append([InlineKeyboardButton(
        "💾 Зберегти відвідуваність",
        callback_data=f"mksave:{class_id}",
    )])
    return InlineKeyboardMarkup(buttons)


async def mark_class_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: coach pressed 'Mark class' button."""
    user_id = update.effective_user.id
    if not config.is_coach(user_id):
        return ConversationHandler.END

    try:
        classes = sheets.get_ended_planned_classes()
    except Exception as exc:
        logger.error("mark_class_start: %s", exc)
        await update.message.reply_text("⚠️ Помилка підключення. Спробуй пізніше.")
        return ConversationHandler.END

    if not classes:
        await update.message.reply_text(
            "Немає занять, які очікують на відмітку.",
            reply_markup=_main_keyboard(user_id),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(_class_label(c), callback_data=f"mk:{c['ClassID']}")]
        for c in classes
    ]
    await update.message.reply_text(
        "Оберіть заняття для відмітки:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return MARK_SELECT_CLASS


async def mark_class_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Coach selected a class — ask if it ran."""
    query = update.callback_query
    await query.answer()
    class_id = query.data.split(":", 1)[1]

    cls = sheets.get_class_by_id(class_id)
    class_label = _class_label(cls) if cls else f"#{class_id}"
    context.user_data["marking_class_id"] = class_id

    await query.edit_message_text(
        f"Заняття *{class_label}*\n\nВоно відбулося?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Так", callback_data=f"mkran:{class_id}:yes"),
            InlineKeyboardButton("❌ Ні", callback_data=f"mkran:{class_id}:no"),
        ]]),
    )
    return MARK_RAN_OR_NOT


async def mark_class_ran(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Coach answered yes/no to 'did the class run?'."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":", 2)  # ["mkran", class_id, "yes|no"]
    class_id, answer = parts[1], parts[2]

    cls = sheets.get_class_by_id(class_id)
    class_label = _class_label(cls) if cls else f"#{class_id}"

    if answer == "yes":
        sheets.update_class_status(class_id, "Done")

        attendance_rows = sheets.get_planned_attendance_rows(class_id)
        if not attendance_rows:
            await query.edit_message_text(
                f"✅ Заняття *{class_label}* позначено як проведене.\n"
                f"Записаних клієнтів не було.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return ConversationHandler.END

        attendees = [
            {
                "client_id": str(r.get("ClientID", "")).strip(),
                "name": str(r.get("Client", "")).strip() or str(r.get("ClientID", "")),
            }
            for r in attendance_rows
        ]
        context.user_data["attendance"] = {
            "class_id": class_id,
            "attendees": attendees,
            "selected": set(),
        }

        await query.edit_message_text(
            f"✅ Заняття *{class_label}* проведено.\n\nПозначте, хто був присутній:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_build_attendance_keyboard(class_id, attendees, set()),
        )
        return ConversationHandler.END

    else:  # no
        sheets.update_class_status(class_id, "Cancelled")
        context.user_data["marking_class_id"] = class_id
        await query.edit_message_text(
            f"❌ Заняття *{class_label}* позначено як скасоване.\n\n"
            f"Вкажіть причину скасування:",
            parse_mode=ParseMode.MARKDOWN,
        )
        return MARK_CANCEL_REASON


async def mark_cancel_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Coach typed a cancellation reason — store it and finish."""
    reason = (update.message.text or "").strip()
    class_id = context.user_data.pop("marking_class_id", None)

    if class_id:
        sheets.set_cancellation_notes(class_id, reason)
        cls = sheets.get_class_by_id(class_id)
        class_label = _class_label(cls) if cls else f"#{class_id}"
        await update.message.reply_text(
            f"✅ Причину скасування заняття *{class_label}* збережено.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_main_keyboard(update.effective_user.id),
        )
    else:
        await update.message.reply_text("✅ Збережено.", reply_markup=_main_keyboard(update.effective_user.id))

    return ConversationHandler.END


async def mark_class_cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fallback /cancel inside the mark-class conversation."""
    context.user_data.pop("marking_class_id", None)
    context.user_data.pop("attendance", None)
    await update.message.reply_text(
        "❌ Відмічення заняття скасовано.",
        reply_markup=_main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END


async def cb_toggle_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle one attendee's presence on/off."""
    query = update.callback_query
    await query.answer()

    if not config.is_coach(query.from_user.id):
        return

    _, class_id, client_id = query.data.split(":", 2)

    att = context.user_data.get("attendance")
    if not att or att["class_id"] != class_id:
        await query.answer("Дані відмітки не знайдено. Почніть заново.", show_alert=True)
        return

    selected: set = att["selected"]
    if client_id in selected:
        selected.discard(client_id)
    else:
        selected.add(client_id)

    await query.edit_message_reply_markup(
        reply_markup=_build_attendance_keyboard(class_id, att["attendees"], selected),
    )


async def cb_save_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save the attendance selection and mark Done / NoShow in the sheet."""
    query = update.callback_query
    await query.answer()

    if not config.is_coach(query.from_user.id):
        return

    class_id = query.data.split(":", 1)[1]
    att = context.user_data.pop("attendance", None)

    if not att or att["class_id"] != class_id:
        await query.edit_message_text("⚠️ Дані відмітки не знайдено. Почніть заново.")
        return

    attended_ids = list(att["selected"])
    sheets.mark_attendance_statuses(class_id, attended_ids)

    cls = sheets.get_class_by_id(class_id)
    class_label = _class_label(cls) if cls else f"#{class_id}"
    done = len(attended_ids)
    noshow = len(att["attendees"]) - done

    await query.edit_message_text(
        f"✅ Відвідуваність збережена для *{class_label}*\n\n"
        f"Були присутні: {done} | Відсутні: {noshow}",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── Coach: view class attendees ──────────────────────────────────────────────

async def _show_class_attendees_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show coach a list of classes that have registered clients."""
    try:
        attendance = sheets._records("2_2_Attendance")
    except Exception as exc:
        logger.error("_show_class_attendees_list: %s", exc)
        await update.message.reply_text("⚠️ Помилка підключення. Спробуй пізніше.")
        return

    planned = [a for a in attendance if str(a.get("AttendanceStatus", "")).strip().lower() == "planned"]
    if not planned:
        await update.message.reply_text("Немає занять із записаними клієнтами.")
        return

    # Build ordered unique class list with count
    seen: dict = {}
    for a in planned:
        cid = str(a.get("ClassID", "")).strip()
        if not cid:
            continue
        if cid not in seen:
            seen[cid] = {
                "ClassID": cid,
                "ClassName": a.get("ClassName", "—"),
                "ClassDate": a.get("ClassDate", ""),
                "ClassStart": a.get("ClassStart", ""),
                "count": 0,
            }
        seen[cid]["count"] += 1

    buttons = [
        [InlineKeyboardButton(
            f"{v['ClassName']} ({_short_datetime(v['ClassDate'], v['ClassStart'])}) — {v['count']} чол.",
            callback_data=f"ca:{v['ClassID']}",
        )]
        for v in seen.values()
    ]
    await update.message.reply_text(
        "Оберіть заняття:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def cb_class_attendees(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show registered clients for the selected class (callback_data = 'ca:<class_id>')."""
    query = update.callback_query
    await query.answer()

    if not config.is_coach(query.from_user.id):
        return

    class_id = query.data.split(":", 1)[1]

    try:
        rows = sheets.get_planned_attendance_rows(class_id)
    except Exception as exc:
        logger.error("cb_class_attendees: %s", exc)
        await query.edit_message_text("⚠️ Помилка підключення. Спробуй пізніше.")
        return

    cls = sheets.get_class_by_id(class_id)
    class_label = _class_label(cls) if cls else f"#{class_id}"

    if not rows:
        await query.edit_message_text(
            f"На заняття *{class_label}* немає записаних клієнтів.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    names = [
        str(r.get("Client", "")).strip() or f"Клієнт #{r.get('ClientID', '?')}"
        for r in rows
    ]
    lines = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(names))
    await query.edit_message_text(
        f"👯‍♀️ *{class_label}*\n\n{lines}\n\nВсього: {len(rows)}",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── UC-6: Coach broadcast ─────────────────────────────────────────────────────

async def coach_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the coach broadcast conversation."""
    user_id = update.effective_user.id
    if not config.is_coach(user_id):
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton("👥 Всім клієнтам", callback_data="ct:all")],
        [InlineKeyboardButton("🏋️ Клієнтам конкретного заняття", callback_data="ct:class")],
    ]
    await update.message.reply_text(
        "Кому надіслати повідомлення?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return COACH_SELECT_TARGET


async def coach_select_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    target = query.data.split(":", 1)[1]
    context.user_data["broadcast_target"] = target

    if target == "all":
        await query.edit_message_text("Введіть текст повідомлення для всіх клієнтів:")
        return COACH_TYPE_MSG

    # Show upcoming classes
    try:
        classes = [c for c in sheets._records("2_1_Classes")
                   if str(c.get("ClassStatus", "")).strip() not in ("Completed", "Cancelled")]
    except Exception as exc:
        logger.error("Sheets error: %s", exc)
        await query.edit_message_text("⚠️ Помилка підключення. Спробуйте ще раз.")
        return ConversationHandler.END

    # Show only classes with Planned registrations
    from sheets import _records as recs
    attendance = recs("2_2_Attendance")
    planned_class_ids = {
        str(a.get("ClassID", "")).strip()
        for a in attendance
        if str(a.get("AttendanceStatus", "")).strip().lower() == "planned"
    }
    classes_with_attendees = [c for c in classes if str(c.get("ClassID", "")) in planned_class_ids]

    if not classes_with_attendees:
        await query.edit_message_text("Немає занять із записаними клієнтами.")
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(_class_label(c), callback_data=f"cc:{c['ClassID']}")]
        for c in classes_with_attendees
    ]
    await query.edit_message_text(
        "Оберіть заняття:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return COACH_SELECT_CLASS


async def coach_select_class(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    class_id = query.data.split(":", 1)[1]
    context.user_data["broadcast_class_id"] = class_id
    cls = sheets.get_class_by_id(class_id)
    context.user_data["broadcast_class_label"] = _class_label(cls) if cls else f"#{class_id}"
    await query.edit_message_text(
        f"Введіть текст повідомлення для клієнтів заняття *{context.user_data['broadcast_class_label']}*:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return COACH_TYPE_MSG


async def coach_receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["broadcast_message"] = update.message.text

    target = context.user_data.get("broadcast_target", "all")
    if target == "all":
        recipients_desc = "всіх клієнтів"
    else:
        recipients_desc = f"клієнтів заняття {context.user_data.get('broadcast_class_label', '')}"

    buttons = [
        [
            InlineKeyboardButton("✅ Надіслати", callback_data="csend:ok"),
            InlineKeyboardButton("❌ Скасувати", callback_data="csend:no"),
        ]
    ]
    await update.message.reply_text(
        f"📢 *Надіслати повідомлення {recipients_desc}?*\n\n"
        f"Текст:\n{update.message.text}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return COACH_CONFIRM


async def coach_confirm_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action == "no":
        await query.edit_message_text("❌ Розсилку скасовано.")
        return ConversationHandler.END

    target = context.user_data.get("broadcast_target", "all")
    message_text = context.user_data.get("broadcast_message", "")

    try:
        if target == "all":
            recipients = sheets.get_all_clients_with_telegram()
        else:
            class_id = context.user_data.get("broadcast_class_id", "")
            recipients = sheets.get_attendees_for_class(class_id)
    except Exception as exc:
        logger.error("Sheets error during broadcast: %s", exc)
        await query.edit_message_text("⚠️ Помилка отримання списку клієнтів.")
        return ConversationHandler.END

    sent, failed = 0, 0
    for r in recipients:
        tg_id = str(r.get("UserTelegramID", "")).strip()
        if not tg_id:
            continue
        try:
            await context.bot.send_message(chat_id=int(tg_id), text=message_text)
            sent += 1
        except Exception as exc:
            logger.warning("Could not send to %s: %s", tg_id, exc)
            failed += 1

    await query.edit_message_text(
        f"✅ Розсилку завершено.\nНадіслано: {sent} | Помилок: {failed}"
    )
    return ConversationHandler.END


async def coach_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Розсилку скасовано.", reply_markup=_main_keyboard(update.effective_user.id))
    return ConversationHandler.END


# ── ConversationHandler for mark-class flow ───────────────────────────────────

def build_mark_class_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BTN_MARK_CLASS)}$"), mark_class_start)],
        states={
            MARK_SELECT_CLASS: [CallbackQueryHandler(mark_class_select, pattern=r"^mk:")],
            MARK_RAN_OR_NOT: [CallbackQueryHandler(mark_class_ran, pattern=r"^mkran:")],
            MARK_CANCEL_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, mark_cancel_reason)],
        },
        fallbacks=[CommandHandler("cancel", mark_class_cancel_conv)],
        allow_reentry=True,
        per_message=False,
    )


# ── ConversationHandler for coach broadcast ──────────────────────────────────

def build_coach_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_BROADCAST}$"), coach_start)],
        states={
            COACH_SELECT_TARGET: [CallbackQueryHandler(coach_select_target, pattern=r"^ct:")],
            COACH_SELECT_CLASS: [CallbackQueryHandler(coach_select_class, pattern=r"^cc:")],
            COACH_TYPE_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, coach_receive_message)],
            COACH_CONFIRM: [CallbackQueryHandler(coach_confirm_send, pattern=r"^csend:")],
        },
        fallbacks=[CommandHandler("cancel", coach_cancel)],
        allow_reentry=True,
        per_message=False,
    )
