from fastapi import FastAPI, Request
from datetime import datetime, timedelta
import os
import threading
import time
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
POSTGRES_URL = os.getenv("POSTGRES_URL")  # e.g., postgres://user:pass@host:port/dbname

# ---------- Ensure DB Tables ----------
def init_db():
    conn = psycopg2.connect(POSTGRES_URL)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id SERIAL PRIMARY KEY,
        chat_id TEXT NOT NULL,
        username TEXT,
        message TEXT,
        send_time TIMESTAMP,
        repeat TEXT DEFAULT 'none',
        repeat_interval INT DEFAULT 1,
        status TEXT DEFAULT 'added'
    )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ---------- Telegram Webhook ----------
@app.post("/telegram-webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    chat = data.get("message", {}).get("chat", {})
    chat_id = chat.get("id")
    username = chat.get("username", "")

    if chat_id:
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO reminders (chat_id, username, message, send_time, status)
            VALUES (%s, %s, %s, %s, 'added')
            ON CONFLICT (chat_id, send_time) DO NOTHING
        """, (str(chat_id), username, "", datetime.now()))
        conn.commit()
        cur.close()
        conn.close()

    return {"ok": True}

# ---------- API: Schedule Reminder ----------
@app.post("/schedule-reminder")
async def schedule_reminder(req: Request):
    data = await req.json()
    chat_id = str(data["chat_id"])
    message = data["message"]
    send_time = datetime.fromisoformat(data["send_time"])
    repeat = data.get("repeat", "none")
    repeat_interval = data.get("repeat_interval", 1)

    conn = psycopg2.connect(POSTGRES_URL)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reminders (chat_id, message, send_time, repeat, repeat_interval, status)
        VALUES (%s, %s, %s, %s, %s, 'scheduled')
    """, (chat_id, message, send_time, repeat, repeat_interval))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "scheduled"}

# ---------- API: List Users ----------
@app.get("/list-users")
async def list_users():
    conn = psycopg2.connect(POSTGRES_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT DISTINCT chat_id, username
        FROM reminders
        WHERE status IN ('added', 'scheduled', 'sent')
    """)
    users = cur.fetchall()
    cur.close()
    conn.close()
    return {"users": users}

# ---------- API: Cancel Reminder ----------
@app.post("/cancel-reminder")
async def cancel_reminder(req: Request):
    data = await req.json()
    chat_id = str(data["chat_id"])
    send_time = data.get("send_time")  # optional: delete specific reminder

    conn = psycopg2.connect(POSTGRES_URL)
    cur = conn.cursor()
    if send_time:
        cur.execute("DELETE FROM reminders WHERE chat_id=%s AND send_time=%s", (chat_id, send_time))
    else:
        cur.execute("DELETE FROM reminders WHERE chat_id=%s", (chat_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "cancelled"}

# ---------- Send Telegram ----------
def send_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except:
        return False

# ---------- Scheduler Loop ----------
def scheduler_loop():
    while True:
        now = datetime.now()
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM reminders WHERE status='scheduled'")
        rows = cur.fetchall()

        for row in rows:
            rowid = row['id']
            chat_id = row['chat_id']
            message = row['message']
            send_time = row['send_time']
            repeat = row['repeat']
            interval = row['repeat_interval']

            if now >= send_time:
                success = send_telegram(chat_id, message)
                status = "sent" if success else "failed"
                # Update send_time for recurring
                if repeat != 'none' and success:
                    next_time = send_time
                    if repeat == "minutes":
                        next_time += timedelta(minutes=interval)
                    elif repeat == "hours":
                        next_time += timedelta(hours=interval)
                    elif repeat == "days":
                        next_time += timedelta(days=interval)
                    elif repeat == "weeks":
                        next_time += timedelta(weeks=interval)
                    elif repeat == "months":
                        next_time += timedelta(days=30*interval)
                    cur.execute("""
                        UPDATE reminders SET send_time=%s, status='scheduled' WHERE id=%s
                    """, (next_time, rowid))
                else:
                    cur.execute("UPDATE reminders SET status=%s WHERE id=%s", (status, rowid))

        conn.commit()
        cur.close()
        conn.close()
        time.sleep(10)

threading.Thread(target=scheduler_loop, daemon=True).start()
