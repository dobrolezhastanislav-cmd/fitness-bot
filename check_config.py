import config
try:
    config.load_config()
    print("BOT_TOKEN OK, SPREADSHEET_ID:", config.SPREADSHEET_ID)
    print("CREDENTIALS_PATH:", config.CREDENTIALS_PATH)
except Exception as e:
    print("CONFIG ERROR:", e)