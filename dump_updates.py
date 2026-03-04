import os, requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("BOT_TOKEN")
resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
print(resp.status_code)
print(resp.text)
