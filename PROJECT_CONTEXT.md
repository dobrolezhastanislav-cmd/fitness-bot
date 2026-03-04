# Be-The-Best Fitness Studio — Telegram Bot

> **This file is the single source of truth for the project.**
> Update it whenever the system changes.

---

## What This Is

A Telegram bot that acts as the studio administrator.
Clients interact with it to register for classes, cancel registrations, and view their profile.
Coaches use it to send mass messages to clients.
Data is stored in Google Sheets — no separate database.

---

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| Bot framework | `python-telegram-bot` v21 (async) | Mature, well-documented, built-in scheduler |
| Sheets access | `gspread` + `google-auth` | Official Google Sheets Python client |
| Reminders | PTB JobQueue (APScheduler) | Built into the bot framework, no extra service |
| Config | `.env` + `config.json` | Non-tech editable, no code changes needed |
| Language | Python 3.11+ | Cross-platform, easy to run |

---

## Project Structure

```
fitness-bot/
├── bot.py               ← ENTRY POINT — run this to start the bot
├── config.py            ← loads .env and config.json
├── sheets.py            ← all Google Sheets read/write logic
├── handlers.py          ← all Telegram message handlers
├── reminders.py         ← reminder scheduler (75 min before class)
├── config.json          ← EDIT THIS: IDs, URLs, file paths
├── .env                 ← EDIT THIS: bot token (keep secret!)
├── .env.example         ← template for .env
├── credentials.json     ← Google service account key (keep secret!)
├── requirements.txt     ← Python dependencies
├── sent_reminders.json  ← auto-managed; tracks sent reminders
├── bot.log              ← auto-created log file
└── files/
    ├── README.txt
    ├── schedule.pdf     ← class schedule (replace when needed)
    └── rules.pdf        ← studio rules document
```

---

## Setup Guide (Step-by-Step)

### 1. Prerequisites

- Python 3.11 or newer installed
- A Telegram account

### 2. Create the Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`, follow the prompts, copy the token
3. Open `.env` (copy `.env.example` to `.env` first) and paste:
   ```
   BOT_TOKEN=123456789:ABCDEF...
   ```

### 3. Google Sheets API Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g. "fitness-bot")
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts** → Create service account
5. Click the account → Keys → Add Key → JSON → Download
6. Rename the downloaded file to `credentials.json` and place it in the bot folder
7. **Share your Google Sheet** with the service account email (looks like `...@...iam.gserviceaccount.com`) with **Editor** access

### 4. Configure config.json

Open `config.json` and fill in:

```json
{
  "owner_telegram_id": 123456789,
  "coach_telegram_ids": [123456789, 987654321],
  "google_spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
  "credentials_file": "credentials.json",
  "instagram_url": "https://www.instagram.com/be_the_best_fitness_studio/",
  "schedule_file": "files/schedule.pdf",
  "rules_file": "files/rules.pdf",
  "timezone": "Europe/Kiev"
}
```

**Finding your Telegram ID:** send any message to @userinfobot.
**Finding the Spreadsheet ID:** it's in the URL:
`https://docs.google.com/spreadsheets/d/`**THIS_PART**`/edit`

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Add Schedule & Rules Files

Place your `schedule.pdf` and `rules.pdf` in the `files/` folder.
Supported formats: PDF, JPG, PNG.

### 7. Run the Bot

```bash
python bot.py
```

To keep it running continuously on a server, use a process manager like `pm2` or `systemd`.

---

## Google Sheet Specification

The bot reads from and writes to three tabs in the spreadsheet.

### Tab: `0_Clients`

| Column | Description | Who updates |
|---|---|---|
| LastName FirstName | Combined display name (formula) | Auto |
| ClientID | Unique client number | Auto (counter) |
| FirstName | Client first name | Studio staff (manual) |
| LastName | Client last name | Studio staff (manual) |
| UserTelegramID | Client's Telegram numeric ID | Studio staff (manual) |
| Email | Email address | Studio staff (manual) |
| Phone | Phone number | Studio staff (manual) |
| BirthDate | Birthday | Studio staff (manual) |
| JoinedOn | Join date | Studio staff (manual) |
| Notes | Internal notes | Studio staff (manual) |
| LastVisit | Last attendance date | Formula (from 2_2_Attendance) |
| ValidPaidAttendances | Remaining paid visits | Formula (from 1_2_Subscriptions) |
| ValidThrough | Subscription expiry date | Formula (from 1_2_Subscriptions) |
| Source | How they found the studio | Studio staff (manual) |

> **Important:** To give a client Telegram bot access, add their numeric Telegram ID to `UserTelegramID`. They can find it by messaging @userinfobot.

### Tab: `2_1_Classes`

| Column | Description | Who updates |
|---|---|---|
| ClassID | Unique class ID | Auto (counter) |
| ClassDate | Class date (DD.MM.YYYY) | Studio (monthly) |
| DayName | Day of week | Formula |
| ClassStart | Start time (HH:MM) | Studio (monthly) |
| ClassEnd | End time | Formula (start + 1h) |
| ClassName | Class name | Studio (monthly) |
| AttendeeLimit | Max participants (always 10) | Studio |
| AttendeeRegistered | Registered count | Formula (from 2_2_Attendance) |
| Attended | Attended count | Formula (from 2_2_Attendance) |
| SlotsRemaining | Free slots | Formula |
| RegistrationIsOpen | **"Open"** = open for registration | Formula |
| CancellationIsAllowed | Whether clients can cancel | Formula |
| ClassStatus | Class status | Manual (drop-down) |
| Note | Optional note | Manual |

### Tab: `2_2_Attendance`

Bot writes here when clients register. Bot updates here when clients cancel.

| Column | Description |
|---|---|
| ClientID | FK → 0_Clients (auto-filled by formula or bot) |
| ClassID | FK → 2_1_Classes (auto-filled by formula or bot) |
| Client | Client full name |
| ClassDate | Date of class |
| ClassStart | Start time |
| ClassEnd | End time |
| ClassName | Class name |
| ClassStatus | Class status (from 2_1_Classes) |
| SlotsRemaining | Slots at time of booking |
| **AttendanceStatus** | **Planned / Cancelled / Attended** — key field |
| CancellationIsAllowed | Whether cancellation is allowed |
| Notes | Optional |

---

## User Flows

### Client Flow (UC-1)

Any message → bot checks `UserTelegramID` in `0_Clients`:
- **Found** → shows main menu keyboard
- **Not found** → asks for phone number; notifies owner

### Register for Class (UC-2)

1. Client taps **"Записатися на заняття"**
2. Bot shows inline buttons for classes where `RegistrationIsOpen = "Open"`
3. Client taps a class → bot re-checks availability
4. Bot appends a row to `2_2_Attendance` with `AttendanceStatus = "Planned"`

### Cancel Registration (UC-3)

1. Client taps **"Скасувати запис"**
2. Bot shows inline buttons for client's rows in `2_2_Attendance` where `AttendanceStatus = "Planned"`
3. Client taps a class → bot checks `CancellationIsAllowed` in `2_1_Classes`
4. If allowed: sets `AttendanceStatus = "Cancelled"` in `2_2_Attendance`

### My Profile (UC-4)

Client taps **"Мій профіль"** → bot reads from `0_Clients` and replies with:
```
Клієнт: Прізвище Ім'я
Абонемент: до DD.MM.YYYY
Лишилося занять: N
Останній візит: DD.MM.YYYY
```

### Reminders (UC-5)

Every minute the bot checks for classes starting in ~75 minutes.
If found, it sends a reminder to all **Planned** attendees.
Sent reminders are tracked in `sent_reminders.json` to prevent duplicates.

### Coach Broadcast (UC-6)

Coach taps **"Розіслати повідомлення"** → conversation:
1. Choose: **Всім клієнтам** or **Клієнтам конкретного заняття**
2. If by class: choose class from list
3. Type message text
4. Confirm → bot sends to all matching clients who have a Telegram ID

---

## Configuration Reference

### `.env`
```
BOT_TOKEN=<your bot token>
```

### `config.json`
| Key | Description |
|---|---|
| `owner_telegram_id` | Telegram ID of the studio owner (receives new-client alerts) |
| `coach_telegram_ids` | List of Telegram IDs with coach access |
| `google_spreadsheet_id` | ID from the Google Sheets URL |
| `credentials_file` | Path to Google service account JSON (default: `credentials.json`) |
| `instagram_url` | Instagram URL sent when client taps Instagram button |
| `schedule_file` | Path to schedule file to send (default: `files/schedule.pdf`) |
| `rules_file` | Path to rules file to send (default: `files/rules.pdf`) |
| `timezone` | Local timezone for reminders (default: `Europe/Kiev`) |

---

## Maintenance Tasks

| Task | How |
|---|---|
| Add a new client | Add a row in `0_Clients`, fill in their Telegram ID |
| Update schedule | Replace `files/schedule.pdf` |
| Update rules | Replace `files/rules.pdf` |
| Add a coach | Add their Telegram ID to `coach_telegram_ids` in `config.json`, restart bot |
| Change owner notification ID | Update `owner_telegram_id` in `config.json`, restart bot |
| Change Instagram URL | Update `instagram_url` in `config.json`, restart bot |
| Add new classes | Add rows to `2_1_Classes` tab in Google Sheet |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Bot doesn't start | Check `BOT_TOKEN` in `.env` |
| "google_spreadsheet_id not set" | Fill in `config.json` |
| "credentials.json not found" | Download service account key and place in bot folder |
| Clients can't access bot | Ensure their `UserTelegramID` is set in `0_Clients` |
| No classes shown for registration | Check that `RegistrationIsOpen = "Open"` in `2_1_Classes` |
| Reminders not sending | Check `bot.log`; verify `UserTelegramID` for clients; check timezone in config |
| Google Sheets errors | Ensure the service account email has Editor access to the sheet |

---

## Roadmap (from original spec)

- [ ] Coach: mark attendance after class (via Poll)
- [ ] Reminder: notify client when subscription is about to expire
- [ ] Reminder: bot posts today's schedule in a dedicated Telegram group

---

## Files to Keep Secret

- `.env` — contains the bot token
- `credentials.json` — Google service account key

**Never share these files or commit them to git.**
