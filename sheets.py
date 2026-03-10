"""
Google Sheets service layer.
All interactions with the spreadsheet go through this module.

Sheet tabs used:
  0_Clients      — client registry
  2_1_Classes    — class schedule
  2_2_Attendance — attendance / registrations
"""
import logging
import time
import os
import json
import tempfile
from datetime import datetime, date, timedelta
from typing import Optional

import pytz
import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ---- Internal state --------------------------------------------------------
_spreadsheet: Optional[gspread.Spreadsheet] = None
_cache: dict = {}
_cache_ts: dict = {}
CACHE_TTL = 60  # seconds; keeps Sheet reads fast, avoids quota issues


# ---- Initialisation --------------------------------------------------------

def init_sheets(spreadsheet_id: str, credentials_path: str = "credentials.json", token_path: str = "token.json") -> None:
    global _spreadsheet
    creds = None

    # Support credentials.json content via env var (for Railway / cloud deployment)
    creds_json_env = os.getenv("GOOGLE_CREDS_JSON")
    if creds_json_env:
        try:
            creds_dict = json.loads(creds_json_env)
            credentials_path = "/tmp/credentials.json"
            with open(credentials_path, "w") as f:
                json.dump(creds_dict, f)
            logger.info("Using Google credentials from GOOGLE_CREDS_JSON env var")
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in GOOGLE_CREDS_JSON: %s", e)
            raise

    # Support token.json content via env var (for Railway / cloud deployment).
    # Generate token.json locally first by running the bot once, then paste
    # its content into the GOOGLE_TOKEN_JSON environment variable on Railway.
    token_json_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json_env:
        try:
            token_data = json.loads(token_json_env)
            creds = Credentials.from_authorized_user_info(token_data, scopes=SCOPES)
            logger.info("Using Google token from GOOGLE_TOKEN_JSON env var")
        except Exception as e:
            logger.error("Invalid GOOGLE_TOKEN_JSON: %s", e)
            raise
    elif os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes=SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Token refresh works without a browser — safe on Railway
            creds.refresh(Request())
            if not token_json_env:
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
        else:
            # First-time OAuth flow — requires a browser, run locally only
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(credentials_path)
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes=SCOPES)
            creds = flow.run_local_server(port=0)
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            logger.info(
                "token.json generated. To deploy on Railway, set the GOOGLE_TOKEN_JSON "
                "environment variable to the contents of token.json."
            )

    client = gspread.authorize(creds)
    _spreadsheet = client.open_by_key(spreadsheet_id)
    logger.info("Connected to Google Sheets: %s", spreadsheet_id)


# ---- Cache helpers ---------------------------------------------------------

def _sheet(name: str) -> gspread.Worksheet:
    assert _spreadsheet is not None, "Call init_sheets() first"
    return _spreadsheet.worksheet(name)


def _records(tab: str, force: bool = False) -> list[dict]:
    """Return all records from a tab, using a short-lived cache."""
    now = time.monotonic()
    if not force and tab in _cache and now - _cache_ts.get(tab, 0) < CACHE_TTL:
        return _cache[tab]
    data = _sheet(tab).get_all_records()
    _cache[tab] = data
    _cache_ts[tab] = now
    return data


def invalidate(*tabs: str) -> None:
    for tab in tabs:
        _cache.pop(tab, None)
        _cache_ts.pop(tab, None)


# ---- Date/time helpers -----------------------------------------------------

DATE_FORMATS = ["%d.%m.%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]

_KYIV_TZ = pytz.timezone("Europe/Kiev")


def _kyiv_now_str() -> str:
    """Return current Kyiv date-time as 'DD.MM.YYYY HH:MM:SS' for DLM column."""
    return datetime.now(_KYIV_TZ).strftime("%d.%m.%Y %H:%M:%S")


def _parse_date(value: str) -> Optional[date]:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_time(value: str) -> Optional[datetime.time]:
    for fmt in ["%H:%M", "%H:%M:%S"]:
        try:
            return datetime.strptime(str(value).strip(), fmt).time()
        except ValueError:
            continue
    return None


def _parse_datetime(date_val: str, time_val: str) -> Optional[datetime]:
    d = _parse_date(date_val)
    t = _parse_time(time_val)
    if d and t:
        return datetime.combine(d, t)
    return None


# ---- 0_Clients -------------------------------------------------------------

def get_client_by_telegram_id(tg_id: int) -> Optional[dict]:
    """Return the client record matching the given Telegram user ID, or None."""
    for row in _records("0_Clients"):
        if str(row.get("UserTelegramID", "")).strip() == str(tg_id):
            return row
    return None


def get_all_clients_with_telegram() -> list[dict]:
    """Return all clients that have a Telegram ID set."""
    return [
        r for r in _records("0_Clients")
        if str(r.get("UserTelegramID", "")).strip()
    ]


# ---- 2_1_Classes -----------------------------------------------------------

def get_open_classes() -> list[dict]:
    """Return classes currently open for registration (computed, no spreadsheet column needed)."""
    return [r for r in _records("2_1_Classes") if is_registration_open(r)]


def get_class_by_id(class_id) -> Optional[dict]:
    for r in _records("2_1_Classes"):
        if str(r.get("ClassID", "")).strip() == str(class_id):
            return r
    return None


def is_registration_open(cls: dict) -> bool:
    """Return True if a class is currently open for registration.

    Rules (all must hold):
    - ClassStatus == 'Planned'
    - ClassDate == today
    - Current time < ClassStart (class has not started yet)
    - SlotsRemaining > 0
    """
    if str(cls.get("ClassStatus", "")).strip().lower() != "planned":
        return False
    if _parse_date(str(cls.get("ClassDate", ""))) != date.today():
        return False
    cls_dt = _parse_datetime(str(cls.get("ClassDate", "")), str(cls.get("ClassStart", "")))
    if cls_dt is None or datetime.now() >= cls_dt:
        return False
    try:
        slots = int(str(cls.get("SlotsRemaining", "0")).strip() or "0")
    except ValueError:
        slots = 0
    return slots > 0


def is_cancellation_allowed(cls: dict) -> bool:
    """Return True if cancellation of a registration is currently allowed.

    Rules (all must hold):
    - ClassStatus == 'Planned'
    - ClassDate == today
    - Class starts more than 30 minutes from now
    Note: SlotsRemaining is NOT checked — cancelling frees a slot.
    """
    if str(cls.get("ClassStatus", "")).strip().lower() != "planned":
        return False
    if _parse_date(str(cls.get("ClassDate", ""))) != date.today():
        return False
    cls_dt = _parse_datetime(str(cls.get("ClassDate", "")), str(cls.get("ClassStart", "")))
    if cls_dt is None:
        return False
    return datetime.now() + timedelta(minutes=30) < cls_dt


def get_upcoming_classes(within_minutes: int = 5, from_now: Optional[datetime] = None) -> list[dict]:
    """
    Return classes whose start time falls in the window
    [from_now + within_minutes - 5, from_now + within_minutes].
    Used by the reminder job to find classes starting 'within_minutes' from now.
    """
    now = from_now or datetime.now()
    target_low = now + timedelta(minutes=within_minutes - 2)
    target_high = now + timedelta(minutes=within_minutes + 2)
    result = []
    for r in _records("2_1_Classes"):
        cls_dt = _parse_datetime(str(r.get("ClassDate", "")), str(r.get("ClassStart", "")))
        if cls_dt and target_low <= cls_dt <= target_high:
            result.append(r)
    return result


# ---- 2_2_Attendance --------------------------------------------------------

def get_planned_registrations(client_id) -> list[dict]:
    """Return all Planned attendance rows for a given client."""
    return [
        r for r in _records("2_2_Attendance")
        if (str(r.get("ClientID", "")).strip() == str(client_id)
            and str(r.get("AttendanceStatus", "")).strip().lower() == "planned")
    ]


def get_attendees_for_class(class_id) -> list[dict]:
    """Return clients registered (Planned) for a specific class."""
    client_ids = {
        str(r.get("ClientID", "")).strip()
        for r in _records("2_2_Attendance")
        if (str(r.get("ClassID", "")).strip() == str(class_id)
            and str(r.get("AttendanceStatus", "")).strip().lower() == "planned")
    }
    return [
        c for c in _records("0_Clients")
        if str(c.get("ClientID", "")).strip() in client_ids
    ]

def is_client_registered_for_class(client_id, class_id) -> bool:
    """Check if a client is already registered (Planned) for a specific class."""
    return any(
        str(r.get("ClientID", "")).strip() == str(client_id)
        and str(r.get("ClassID", "")).strip() == str(class_id)
        and str(r.get("AttendanceStatus", "")).strip().lower() == "planned"
        for r in _records("2_2_Attendance")
    )

def register_client(client: dict, cls: dict) -> tuple[bool, str]:
    """
    Add a new Planned row to 2_2_Attendance, or reactivate a Cancelled one.
    Returns (success: bool, error_key: str).
    error_key is '' on success, 'closed', 'full', or 'already_registered' otherwise.
    """
    # Force-refresh both tabs so SlotsRemaining and attendance status
    # always reflect the live sheet state, not a stale 60s cache.
    invalidate("2_1_Classes", "2_2_Attendance")

    # Check if client is already registered for this class
    if is_client_registered_for_class(client["ClientID"], cls["ClassID"]):
        return False, "already_registered"

    # Re-check with fresh data
    fresh_cls = get_class_by_id(cls["ClassID"])
    if not fresh_cls:
        return False, "closed"
    if str(fresh_cls.get("ClassStatus", "")).strip().lower() != "planned":
        return False, "closed"
    if _parse_date(str(fresh_cls.get("ClassDate", ""))) != date.today():
        return False, "closed"
    cls_dt = _parse_datetime(str(fresh_cls.get("ClassDate", "")), str(fresh_cls.get("ClassStart", "")))
    if cls_dt is None or datetime.now() >= cls_dt:
        return False, "closed"
    try:
        slots = int(str(fresh_cls.get("SlotsRemaining", "0")).strip() or "0")
    except ValueError:
        slots = 0
    if slots <= 0:
        return False, "full"

    # If a Cancelled row already exists for this client+class, reactivate it
    # instead of inserting a duplicate row.
    try:
        ws = _sheet("2_2_Attendance")
        all_values = ws.get_all_values()
        if all_values:
            headers = all_values[0]
            lc = [h.strip().lower() for h in headers]
            try:
                client_col = lc.index('clientid')
                class_col = lc.index('classid')
                status_col = lc.index('attendancestatus')
                for idx, row_vals in enumerate(all_values[1:], start=2):
                    if (str(row_vals[client_col]).strip() == str(client["ClientID"])
                            and str(row_vals[class_col]).strip() == str(cls["ClassID"])
                            and str(row_vals[status_col]).strip().lower() == "cancelled"):
                        ws.update_cell(idx, status_col + 1, "Planned")
                        try:
                            dlm_col = lc.index("dlm") + 1
                            ws.update_cell(idx, dlm_col, _kyiv_now_str())
                        except (ValueError, Exception):
                            pass
                        invalidate("2_2_Attendance", "2_1_Classes")
                        return True, ""
            except ValueError:
                pass  # headers not found — fall through to insert
    except Exception as exc:
        logger.warning("Could not check for cancelled registration: %s", exc)

    # Build the row to append. According to the project spec, only a handful
    # of columns are considered "user input" – the bot should write the client
    # name, date, class name and the attendance status. Everything else in the
    # `2_2_Attendance` tab is derived by formulas (client/class IDs, start/end
    # times, slots remaining, etc.), so we deliberately leave those cells empty
    # and let the sheet compute them.
    # use precomputed "LastName FirstName" field if available; else combine
    client_name = str(client.get('LastName FirstName') or
                      f"{client.get('LastName', '')} {client.get('FirstName', '')}").strip()
    # columns: ClientID, ClassID, Client, ClassDate, ClassStart, ClassEnd,
    # ClassName, ClassStatus, SlotsRemaining, AttendanceStatus, Notes
    row = [
        "",                              # ClientID (formula)
        "",                              # ClassID (formula)
        client_name,                      # Client
        str(cls.get("ClassDate", "")), # ClassDate
        "",                              # ClassStart (formula)
        "",                              # ClassEnd (formula)
        str(cls.get("ClassName", "")), # ClassName
        "",                              # ClassStatus (formula)
        "",                              # SlotsRemaining (formula)
        "Planned",                       # AttendanceStatus
        "",                              # Notes
    ]
    try:
        ws = _sheet("2_2_Attendance")

        # get current values and sheet metadata
        all_values = ws.get_all_values()
        headers = all_values[0] if all_values else []
        row_count = len(all_values)
        col_count = max(len(headers), len(row), ws.col_count or 0)

        sheet_id = ws._properties.get('sheetId') if ws._properties else None
        if not sheet_id:
            # fallback to simple append if sheetId not available
            ws.append_row(row, value_input_option="USER_ENTERED")
            invalidate("2_2_Attendance", "2_1_Classes")
            return True, ""

        # Insert a new row inside the sheet at the end of current data (this
        # ensures the sheet's table/range expands correctly), then copy the
        # previous row (formulas & formatting) into the inserted row.
        insert_idx = row_count  # zero-based index where to insert
        requests = []
        requests.append({
            'insertDimension': {
                'range': {
                    'sheetId': sheet_id,
                    'dimension': 'ROWS',
                    'startIndex': insert_idx,
                    'endIndex': insert_idx + 1,
                },
                'inheritFromBefore': True,
            }
        })

        # copy previous row into the new row
        if row_count >= 1:
            prev_row_idx = row_count - 1
            requests.append({
                'copyPaste': {
                    'source': {
                        'sheetId': sheet_id,
                        'startRowIndex': prev_row_idx,
                        'endRowIndex': prev_row_idx + 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': col_count,
                    },
                    'destination': {
                        'sheetId': sheet_id,
                        'startRowIndex': insert_idx,
                        'endRowIndex': insert_idx + 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': col_count,
                    },
                    'pasteType': 'PASTE_NORMAL',
                    'pasteOrientation': 'NORMAL',
                }
            })

        ws.spreadsheet.batch_update({'requests': requests})

        # Now write only the fields we control into the newly inserted row
        # Locate header indices for the target columns
        lc = [h.strip().lower() for h in headers]
        def col_idx(name):
            try:
                return lc.index(name) + 1
            except ValueError:
                return None

        client_col = col_idx('client') or 3
        classdate_col = col_idx('classdate') or 4
        classname_col = col_idx('classname') or 7
        status_col = col_idx('attendancestatus') or 10
        dlm_col = col_idx('dlm')

        new_row_1based = insert_idx + 1
        try:
            ws.update_cell(new_row_1based, client_col, client_name)
            ws.update_cell(new_row_1based, classdate_col, str(cls.get('ClassDate', '')))
            ws.update_cell(new_row_1based, classname_col, str(cls.get('ClassName', '')))
            ws.update_cell(new_row_1based, status_col, 'Planned')
            if dlm_col:
                ws.update_cell(new_row_1based, dlm_col, _kyiv_now_str())
        except Exception as exc:
            logger.warning('Could not write attendance fields into new row: %s', exc)

        invalidate("2_2_Attendance", "2_1_Classes")
        return True, ""
    except Exception as exc:
        logger.error("Error registering client: %s", exc)
        return False, "error"


def get_ended_planned_classes() -> list[dict]:
    """Return all Planned classes up to and including today (coach can mark past/today)."""
    today = date.today()
    result = []
    for r in _records("2_1_Classes", force=True):
        if str(r.get("ClassStatus", "")).strip().lower() != "planned":
            continue
        cls_date = _parse_date(str(r.get("ClassDate", "")))
        if cls_date is None or cls_date > today:
            continue
        result.append(r)
    # Sort oldest first so list is chronological
    result.sort(key=lambda r: _parse_date(str(r.get("ClassDate", ""))) or date.min)
    return result


def update_class_status(class_id, new_status: str) -> bool:
    """Update ClassStatus for a class row in 2_1_Classes."""
    ws = _sheet("2_1_Classes")
    all_values = ws.get_all_values()
    if not all_values:
        return False
    headers = all_values[0]
    lc = [h.strip().lower() for h in headers]
    try:
        id_col = lc.index("classid")
        status_col = lc.index("classstatus")
    except ValueError:
        return False
    for idx, row in enumerate(all_values[1:], start=2):
        if len(row) > id_col and str(row[id_col]).strip() == str(class_id):
            ws.update_cell(idx, status_col + 1, new_status)
            invalidate("2_1_Classes")
            return True
    return False


def get_planned_attendance_rows(class_id) -> list[dict]:
    """Return Planned attendance rows for a class."""
    return [
        r for r in _records("2_2_Attendance")
        if (str(r.get("ClassID", "")).strip() == str(class_id)
            and str(r.get("AttendanceStatus", "")).strip().lower() == "planned")
    ]


def mark_attendance_statuses(class_id, attended_client_ids: list) -> bool:
    """Set AttendanceStatus to Done or NoShow for all Planned rows of a class."""
    ws = _sheet("2_2_Attendance")
    all_values = ws.get_all_values()
    if not all_values:
        return False
    headers = all_values[0]
    lc = [h.strip().lower() for h in headers]
    try:
        class_col = lc.index("classid")
        client_col = lc.index("clientid")
        status_col = lc.index("attendancestatus")
    except ValueError:
        return False
    dlm_col = lc.index("dlm") + 1 if "dlm" in lc else None
    attended_set = {str(cid) for cid in attended_client_ids}
    updated = False
    for idx, row in enumerate(all_values[1:], start=2):
        if (len(row) > max(class_col, client_col, status_col)
                and str(row[class_col]).strip() == str(class_id)
                and str(row[status_col]).strip().lower() == "planned"):
            new_status = "Done" if str(row[client_col]).strip() in attended_set else "NoShow"
            ws.update_cell(idx, status_col + 1, new_status)
            if dlm_col:
                ws.update_cell(idx, dlm_col, _kyiv_now_str())
            updated = True
    if updated:
        invalidate("2_2_Attendance")
    return updated


def set_cancellation_notes(class_id, reason: str) -> bool:
    """Write cancellation reason into Notes column of the class row in 2_1_Classes."""
    ws = _sheet("2_1_Classes")
    all_values = ws.get_all_values()
    if not all_values:
        return False
    headers = all_values[0]
    lc = [h.strip().lower() for h in headers]
    try:
        id_col = lc.index("classid")
        notes_col = lc.index("notes")
    except ValueError:
        return False
    for idx, row in enumerate(all_values[1:], start=2):
        if len(row) > max(id_col, notes_col) and str(row[id_col]).strip() == str(class_id):
            ws.update_cell(idx, notes_col + 1, reason)
            invalidate("2_1_Classes")
            return True
    return False


def cancel_registration(client_id, class_id) -> tuple[bool, str]:
    """
    Set AttendanceStatus to 'Cancelled' for a Planned row.
    Returns (success: bool, error_key: str).
    error_key: '' on success, 'not_allowed' or 'not_found'.
    """
    cls = get_class_by_id(class_id)
    if not cls:
        return False, "not_found"

    if not is_cancellation_allowed(cls):
        return False, "not_allowed"

    ws = _sheet("2_2_Attendance")
    all_values = ws.get_all_values()
    if not all_values:
        return False, "not_found"

    headers = all_values[0]

    # locate important columns by header name
    lc = [h.strip().lower() for h in headers]
    try:
        client_col = lc.index('clientid')
        class_col = lc.index('classid')
        status_col = lc.index('attendancestatus')
    except ValueError:
        return False, "not_found"
    dlm_col = lc.index('dlm') + 1 if 'dlm' in lc else None

    # find the row with matching client and class and status Planned
    for idx, row_vals in enumerate(all_values[1:], start=2):
        try:
            if str(row_vals[client_col]).strip() == str(client_id) and str(row_vals[class_col]).strip() == str(class_id) and str(row_vals[status_col]).strip().lower() == "planned":
                ws.update_cell(idx, status_col + 1, 'Cancelled')
                if dlm_col:
                    ws.update_cell(idx, dlm_col, _kyiv_now_str())
                invalidate('2_2_Attendance', '2_1_Classes')
                return True, ''
        except Exception:
            continue

    return False, 'not_found'
