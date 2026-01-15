# telegram_backend.py
from fastapi import FastAPI, Request
from datetime import datetime
import sqlite3
import os
import threading
import time
import requests

app = FastAPI()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

DB_FILE = "reminders.db"

# ---------- Create DB ----------
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    chat_id TEXT,
    message TEXT,
    send_time TEXT,
    status TEXT
)
""")
conn.commit()
conn.close()

# ---------- Telegram Webhook (for new users) ----------
@app.post("/telegram-webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    chat = data.get("message", {}).get("chat", {})
    chat_id = chat.get("id")
    username = chat.get("username", "")
    first_name = chat.get("first_name", "")
    if chat_id:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO reminders (chat_id,message,send_time,status) VALUES (?,?,?,?)",
                  (str(chat_id), "", datetime.now().isoformat(), "added"))
        conn.commit()
        conn.close()
    return {"ok": True}

# ---------- Function to send Telegram message ----------
def send_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except:
        return False

# ---------- Background scheduler ----------
def scheduler_loop():
    while True:
        now = datetime.now()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT rowid, chat_id, message, send_time FROM reminders WHERE status='scheduled'")
        rows = c.fetchall()
        for rowid, chat_id, message, send_time_str in rows:
            send_time = datetime.fromisoformat(send_time_str)
            if now >= send_time:
                success = send_telegram(chat_id, message)
                status = "sent" if success else "failed"
                c.execute("UPDATE reminders SET status=? WHERE rowid=?", (status, rowid))
        conn.commit()
        conn.close()
        time.sleep(10)  # check every 10 seconds

# ---------- Start scheduler in background thread ----------
threading.Thread(target=scheduler_loop, daemon=True).start()
