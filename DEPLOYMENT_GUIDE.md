# Deployment Guide: Railway (Cloud)

> **For:** Fitness Bot (Telegram Bot)  
> **Difficulty:** Beginner-friendly  
> **Cost:** Free tier available (~$5/month for reliable uptime)  
> **Setup Time:** ~15 minutes

---

## Why Railway?

✅ **Free tier** — $5/month free credits (more than enough for your bot)  
✅ **Simple** — Connect GitHub, deploy in 1 click  
✅ **Reliable** — Always-on, no wake-up delays  
✅ **Automatic restarts** — Bot stays online 24/7  
✅ **Environment variables** — Easy to manage secrets (.env, credentials.json)

---

## Step 1: Prepare Your Code for Cloud

### 1.1 Create a GitHub repository

1. Go to [github.com](https://github.com) and sign in (create account if needed)
2. Click **New repository**
3. Name it: `fitness-bot`
4. Choose **Public** (Railway can see it)
5. Click **Create repository**

### 1.2 Upload your code to GitHub

On your laptop, open PowerShell in the `fitness-bot` folder:

```powershell
cd c:\Users\stanislav.dobrolezha\fitness-bot
git init
git add .
git commit -m "Initial commit: fitness bot ready for deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/fitness-bot.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

**What files are uploaded?**
- `bot.py`, `handlers.py`, `sheets.py`, `reminders.py`, `config.py`
- `config.json`, `requirements.txt`
- `files/` (schedule.pdf, rules.pdf)

⚠️ **DO NOT commit these files** (they contain secrets):
- `.env` (bot token)
- `credentials.json` (Google service account)
- `token.json` (Google auth token)

Create a `.gitignore` file to prevent accidents:

```
.env
credentials.json
token.json
*.pyc
__pycache__/
.DS_Store
bot.log
sent_reminders.json
```

Save it in the fitness-bot folder and push:

```powershell
git add .gitignore
git commit -m "Add .gitignore"
git push
```

---

## Step 2: Set Up Railway

### 2.1 Create Railway account

1. Go to [railway.app](https://railway.app)
2. Click **Sign up**
3. Use GitHub (easiest) or email
4. Authorize Railway to access your GitHub account

### 2.2 Create a new project

1. Click **New Project**
2. Select **Deploy from GitHub**
3. Click **Connect GitHub** and authorize
4. Find and select your `fitness-bot` repository
5. Click **Deploy**

Railway will:
- Detect it's a Python project
- Read `requirements.txt`
- Install dependencies
- Try to start the bot

**It will fail** — but that's expected. We need to add environment variables first.

---

## Step 3: Add Secrets (Environment Variables)

### 3.1 Add BOT_TOKEN

1. In Railway Dashboard, go to your `fitness-bot` project
2. Click the **fitness-bot** service (blue box)
3. Click **Variables** tab
4. Click **+ New Variable**

**Name:** `BOT_TOKEN`  
**Value:** `paste your token here` (from `.env` locally)

Click **Add**

### 3.2 Add Google credentials

You need to upload `credentials.json` (the service account key from Google).

1. Click **+ New Variable** again
2. **Name:** `GOOGLE_CREDS_JSON`
3. **Value:** Copy the entire contents of your `credentials.json` file and paste it

Example structure:
```json
{"type": "service_account", "project_id": "...", "private_key": "...", ...}
```

Click **Add**

### 3.3 Update your code to read from environment

Edit `sheets.py` to use the environment variable:

Find this line:
```python
def init_sheets(spreadsheet_id: str, credentials_path: str = "credentials.json", token_path: str = "token.json") -> None:
```

Change it to:

```python
def init_sheets(spreadsheet_id: str, credentials_path: str = None, token_path: str = "token.json") -> None:
    import os
    import json
    from pathlib import Path
    
    # If credentials_path is not provided, try to use environment variable
    if credentials_path is None:
        creds_json = os.getenv("GOOGLE_CREDS_JSON")
        if creds_json:
            # Write the JSON to a temporary file
            creds_data = json.loads(creds_json)
            credentials_path = "/tmp/credentials.json"
            with open(credentials_path, "w") as f:
                json.dump(creds_data, f)
        else:
            credentials_path = "credentials.json"
```

Then commit and push:

```powershell
git add sheets.py
git commit -m "Support environment variable for Google credentials"
git push
```

Railway will auto-redeploy.

---

## Step 4: Verify Deployment

### 4.1 Check logs

In Railway:
1. Click your project → **fitness-bot** service
2. Click **Logs** tab
3. Watch for startup messages

**Success looks like:**
```
[INFO] Configuration loaded OK
[INFO] Google Sheets connected OK
[INFO] Bot started successfully
```

**If you see errors:**
- Check that `BOT_TOKEN` is correct (no extra spaces)
- Verify `GOOGLE_CREDS_JSON` is valid JSON
- Check `config.json` has the correct Spreadsheet ID

### 4.2 Test the bot

Send `/start` to your bot on Telegram. It should respond immediately.

---

## Step 5: Keep It Running 24/7

Railway services stay online indefinitely. No extra action needed! ✅

---

## Step 6: Monitor & Maintain

### View logs anytime:
- Railway Dashboard → Your project → **Logs**

### Update code:
```powershell
git add .
git commit -m "Bug fix or feature update"
git push
```

Railway auto-deploys on push.

### Update secrets:
Railway Dashboard → **Variables** → Edit and save

The bot restarts ~30 seconds after any variable change.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot doesn't start | Check Logs tab in Railway. Look for error messages. |
| "Credentials invalid" | Verify the JSON in `GOOGLE_CREDS_JSON` is complete and valid. |
| Bot goes offline | Railway keeps it running unless the service crashes. Check Logs. |
| Changes not reflected | Must push to GitHub. Railway auto-deploys within 1 min. |
| Files missing (schedule.pdf, rules.pdf) | Upload them to `files/` folder, commit, and push. |

---

## Cost Breakdown

- **Free tier:** $5/month credit  
- **Typical monthly cost:** $0-2 (stays within free tier)
- **Premium:** If you need extra resources, $7/month for reliability

Your bot should cost nothing for years.

---

## Next Steps

1. ✅ Prepare code (add `.gitignore`)
2. ✅ Push to GitHub
3. ✅ Create Railway account
4. ✅ Deploy project
5. ✅ Add secret variables
6. ✅ Update code for environment variables
7. ✅ Test with `/start`
8. ✅ Monitor logs daily for first week

---

## Emergency: Restart Bot

If the bot becomes unresponsive:

1. Railway Dashboard → **fitness-bot** → **Settings**
2. Click **Redeploy** button
3. Wait 30 seconds for restart

---

## Back Up Your Data

**Every week**, export your Google Sheet as CSV backup:
1. Open your fitness-bot sheet
2. File → Download → CSV (all tabs)
3. Save locally

Google Sheets is your database — it's already backed up to Google's servers.

