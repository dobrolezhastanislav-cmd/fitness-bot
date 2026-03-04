# Fitness Bot — Manual Test Cases for Smartphone

> **Date:** March 4, 2026  
> **Target Device:** Smartphone with Telegram  
> **Bot Status:** [Production/Testing]  
> **Tester Name:** _______________  
> **Date Tested:** _______________

---

## Test Environment Setup

Before running any tests:
1. Bot must be running: `python bot.py`
2. Have access to the Google Sheet (verify data synchronizes in real-time)
3. Use a fresh Telegram account if testing for the first time
4. Have a second Telegram account for testing multi-user scenarios
5. Verify network connectivity

---

## Test Execution Notes

For each test case:
- **PASS**: Outcome matches expected result
- **FAIL**: Outcome differs from expected
- **N/A**: Test not applicable in this environment
- Add notes in the "Result & Notes" column
- Include screenshot references if needed

---

---

# UC-1: FIRST CONTACT — Unknown User Registration

### Common Preconditions
- Bot is running and reachable
- The Telegram account used is not listed in `0_Clients`
- Network connectivity available

#### TC-1.1: New User Receives Phone Number Request

**Objective:** Verify that a user not in the database is prompted for phone number

**Steps:**
1. Open Telegram and find the fitness bot
2. Send `/start` command
3. Observe the response

**Expected Result:**
- Bot displays prompt asking for phone number
- Button "📱 Поділитися номером телефону" appears
- Fallback text explains manual entry

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-1.2: Phone Number Shared via Button

**Additional Preconditions:**
- TC‑1.1 has been completed successfully
- Device supports contact sharing

**Steps:**
1. Tap the contact‑share button
2. Share the current/selected number
3. Observe bot reply

**Expected Result:**
- Bot thanks user and provides the same button again
- Owner receives notification containing phone, TelegramID, username, full name

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-1.3: Phone Number Shared via Manual Text

**Additional Preconditions:**
- Contact button unavailable (web client or similar)

**Steps:**
1. Type a phone number (digits and optional +)
2. Send the message

**Expected Result:**
- Bot accepts number and behaves as in TC‑1.2
- Non‑numeric input is ignored or triggers menu re‑display

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-1.4: New User Added to Database

**Additional Preconditions:**
- Owner has manually added the user to `0_Clients` with a valid `UserTelegramID`

**Steps:**
1. Send any message to the bot after being added

**Expected Result:**
- Bot recognizes user and displays the client main menu

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

---

# UC-2: REGISTER FOR CLASS

### Common Preconditions
- User exists in `0_Clients`
- `2_1_Classes` tab is populated with at least one upcoming class
- Google Sheets connection is working

#### TC-2.1: View Available Classes

**Additional Preconditions:**
- The sheet contains one open class for today with slots, one closed/not‑today class, and one past class

**Steps:**
1. Tap "📝 Записатися на заняття"
2. Review the list of classes displayed

**Expected Result:**
- Only classes open for registration appear
- Buttons are labelled `ClassName (DD.MM - HH:MM)`
- No closed or past classes shown

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-2.2: No Available Classes

**Additional Preconditions:**
- All classes either closed or not meet open criteria

**Steps:**
1. Tap the register button

**Expected Result:**
- Bot replies "На сьогодні немає занять, доступних для запису. 😔"
- No selection buttons are shown

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-2.3: Successful Registration

**Additional Preconditions:**
- The chosen class has available slots and the user has not already booked it

**Steps:**
1. Select an open class from the list
2. Observe the confirmation message
3. Verify a new row in `2_2_Attendance`

**Expected Result:**
- Confirmation text with class name and formatted date/time
- Sheet row with appropriate fields (`AttendanceStatus = "Planned"` etc.)

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-2.4: Duplicate Registration Prevention

**Additional Preconditions:**
- User already has a "Planned" entry for that class

**Steps:**
1. Attempt to register again for the same class

**Expected Result:**
- Bot replies "Ви вже записані на це заняття. 😊"
- No duplicate row added

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-2.5: Registration Closed After Initial View

**Additional Preconditions:**
- Administrator modifies the class (status/date) while the user is viewing the menu

**Steps:**
1. Tap the now‑closed class

**Expected Result:**
- Bot replies that registration has closed and does not add a row

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-2.6: Class Full — No More Slots

**Additional Preconditions:**
- Class has `SlotsRemaining` equal to zero

**Steps:**
1. Try to select the full class (it may not appear)

**Expected Result:**
- Either class is hidden from the list or the bot responds it's full

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-2.7: Sheet Connection Error During Registration

**Additional Preconditions:**
- Ability to simulate network loss

**Steps:**
1. Disconnect internet after selecting a class but before confirm

**Expected Result:**
- Bot shows "⚠️ Помилка запису..." and user can retry later

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

---

# UC-3: CANCEL REGISTRATION

### Common Preconditions
- User has at least one planned registration in `2_2_Attendance`
- Sheets API accessible

#### TC-3.1: View Registered Classes

**Steps:**
1. Tap "❌ Скасувати запис"
2. Review the list of classes

**Expected Result:**
- All planned registrations appear with proper formatting

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-3.2: No Active Registrations

**Additional Preconditions:**
- The user has no Planned entries

**Steps:**
1. Tap cancellation button

**Expected Result:**
- Bot replies "Ви не записані на жодне заняття. 😊"

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-3.3: Successful Cancellation

**Additional Preconditions:**
- Target class allows cancellation (starts >30 min later)

**Steps:**
1. Select the class to cancel

**Expected Result:**
- Confirmation message sent
- Sheet row updated to `AttendanceStatus = "Cancelled"`

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-3.4: Cancellation Not Allowed

**Additional Preconditions:**
- Class start less than 30 min away or cancellations locked

**Steps:**
1. Attempt to cancel

**Expected Result:**
- Bot replies cancellation not possible
- Sheet unchanged

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-3.5: Sheet Connection Error During Cancellation

**Additional Preconditions:**
- Ability to cut connection mid‑flow

**Steps:**
1. Disconnect before confirming cancellation

**Expected Result:**
- Bot returns error and keeps status planned

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

---

# UC-4: VIEW PROFILE INFORMATION

### Common Preconditions
- User exists in `0_Clients`
- Sheets API accessible

#### TC-4.1: View Complete Profile

**Additional Preconditions:**
- `0_Clients` row has all fields populated and at least one planned class

**Steps:**
1. Tap "👤 Мій профіль"

**Expected Result:**
- Profile message shows all fields and list of planned classes

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-4.2: Profile with Missing Fields

**Additional Preconditions:**
- Some fields (e.g. ValidThrough) are empty in sheet

**Steps:**
1. View profile

**Expected Result:**
- Missing fields display as "—" and layout stays clean

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-4.3: No Planned Classes in Profile

**Additional Preconditions:**
- User has no Planned registrations

**Steps:**
1. View profile

**Expected Result:**
- Profile shows but omits the "Заплановані заняття" section

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-4.4: Profile Data Updates After Registration

**Additional Preconditions:**
- User registers for a new class after initially viewing profile

**Steps:**
1. Register for a class
2. Open profile again

**Expected Result:**
- Newly registered class appears in the profile list

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-4.5: Sheet Connection Error During Profile View

**Additional Preconditions:**
- Capability to simulate network outage

**Steps:**
1. Disconnect and then tap "👤 Мій профіль"

**Expected Result:**
- Bot shows error message and no partial data

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

---

# UC-5: AUTOMATIC REMINDERS — REMOVED

> **⚠️ The reminder scheduler was removed from the bot; all TC‑5.x cases are N/A.**

---

# UC-6: COACH BROADCAST — Send Mass Messages

### Common Preconditions
- Coach Telegram ID listed in `config.json`
- At least one client with Telegram ID present
- Sheets API working

#### TC-6.1: Coach Menu Access

**Steps:**
1. Coach sends `/start`

**Expected Result:**
- Only the broadcast button is shown on the keyboard

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.2: Broadcast to All Clients

**Additional Preconditions:**
- Minimum three valid client IDs exist

**Steps:**
1. Start broadcast → select "Всім клієнтам" → type message → confirm

**Expected Result:**
- Message delivered to every valid client
- Final status shows sent/failed counts

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.3: Broadcast to Specific Class

**Additional Preconditions:**
- Two classes with different attendee sets exist

**Steps:**
1. Choose class‑specific target → pick class A → send message

**Expected Result:**
- Only class A’s attendees receive the message

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.4: Only Classes with Attendees Shown

**Additional Preconditions:**
- At least two classes have planned registrations; others are empty/closed

**Steps:**
1. Initiate class‑specific broadcast

**Expected Result:**
- Only classes with registrations are listed

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.5: No Classes Available for Class-Specific Broadcast

**Additional Preconditions:**
- No class currently has planned registrations

**Steps:**
1. Attempt class‑specific broadcast

**Expected Result:**
- Bot replies "Немає занять із записаними клієнтами." and ends flow

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.6: Coach Preview & Confirm Message

**Steps:**
1. Type broadcast text → review confirmation screen

**Expected Result:**
- Message displayed for verification with ✅/❌ options

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.7: Coach Cancels Broadcast

**Steps:**
1. At confirmation step tap ❌

**Expected Result:**
- Bot states "Розсилку скасовано." and aborts

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.8: Broadcast with Long Message

**Steps:**
1. Send multi‑line text as broadcast

**Expected Result:**
- Entire message arrives intact with line breaks

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.9: Broadcast with Special Characters

**Steps:**
1. Include emojis/symbols/@mentions in broadcast

**Expected Result:**
- Characters render correctly on client side

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.10: Partial Send Failure Handling

**Additional Preconditions:**
- At least one invalid Telegram ID present

**Steps:**
1. Broadcast to all clients

**Expected Result:**
- Report shows counts of successes and failures

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.11: Non-Coach Cannot Broadcast

**Additional Preconditions:**
- Use a regular client account

**Steps:**
1. Look for broadcast button/send command

**Expected Result:**
- No broadcast option accessible; commands ignored

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

#### TC-6.12: Sheet Connection Error During Broadcast

**Additional Preconditions:**
- Ability to disable network during broadcast

**Steps:**
1. Disconnect after selecting recipients but before sending

**Expected Result:**
- Bot returns an error or partial send report without crashing

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

---

# ADDITIONAL FEATURES

## TC-7.1: View Schedule File

**Common Preconditions:**
- `config.SCHEDULE_FILE` points to an existing PDF/JPG/PNG

**Steps:**
1. Tap "📅 Розклад"

**Expected Result:**
- File is delivered or appropriate error message

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

## TC-7.2: View Rules File

**Common Preconditions:**
- `config.RULES_FILE` exists

**Steps:**
1. Tap "📋 Правила студії"

**Expected Result:**
- File sent or error text

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

## TC-7.3: Instagram Link

**Common Preconditions:**
- `config.INSTAGRAM_URL` set

**Steps:**
1. Tap "📸 Instagram"

**Expected Result:**
- Correct clickable URL message

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

## TC-7.4: Return to Main Menu

**Common Preconditions:**
- User is anywhere in the conversation

**Steps:**
1. Send unrecognized text or `/menu`

**Expected Result:**
- Main keyboard reappears

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

---

# EDGE CASES & STRESS TESTS

## TC-8.1: Rapid Registration/Cancellation

**Common Preconditions:**
- At least two open classes

**Steps:**
1. Quickly register and cancel multiple times

**Expected Result:**
- Bot remains stable and sheet accurate

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

## TC-8.2: Very Long Class Name

**Steps:**
1. Observe UI with an abnormally long class name

**Expected Result:**
- Text wraps/truncates gracefully; no crashes

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

## TC-8.3: Rapid Reminders (N/A)

> Reminders feature removed; skip this test

**Result & Notes:** ☒ N/A

---

## TC-8.4: Very Old Classes (Date in Past)

**Steps:**
1. Add a past‑date class and attempt registration

**Expected Result:**
- Class ignored; no errors

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

## TC-8.5: Timezone Edge Cases (N/A)

> Reminders removed

**Result & Notes:** ☒ N/A

---

## TC-8.6: Spam/Abuse — Rapid Invalid Inputs

**Steps:**
1. Send various malformed messages quickly

**Expected Result:**
- Bot handles gracefully; no crashes

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

## TC-8.7: Concurrent Users

**Common Preconditions:**
- Five or more test accounts

**Steps:**
1. All users simultaneously book the same class

**Expected Result:**
- Registrations succeed up to limit; no duplicates or errors

**Result & Notes:** ☐ PASS ☐ FAIL ☐ N/A
```
_________________________________________________________________
_________________________________________________________________
```

---

---

# SIGN-OFF

## Test Summary

| Feature | Passed | Failed | N/A | Comments |
|---------|--------|--------|-----|----------|
| UC-1: First Contact | ☐ | ☐ | ☐ | |
| UC-2: Register | ☐ | ☐ | ☐ | |
| UC-3: Cancel | ☐ | ☐ | ☐ | |
| UC-4: Profile | ☐ | ☐ | ☐ | |
| UC-5: Reminders | ☐ | ☐ | ☐ | |
| UC-6: Broadcast | ☐ | ☐ | ☐ | |
| Additional Features | ☐ | ☐ | ☐ | |
| Edge Cases | ☐ | ☐ | ☐ | |

**Total Test Cases:** 73  
**Date Tested:** _______________  
**Tester Name:** _______________  
**Overall Status:** ☐ PASS ☐ FAIL ☐ PARTIAL

### Issues Found

```
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
```

### Recommendations for Production

```
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
```

### Sign-Off

**Tester:** _____________________ Date: _______________

**Product Owner:** _____________________ Date: _______________

---

## Notes for Future Runs

- Keep this document as a baseline for regression testing
- Update after any code changes
- Add new test cases as new features are added
- Document any environment-specific issues
- Archive dated test runs for compliance

