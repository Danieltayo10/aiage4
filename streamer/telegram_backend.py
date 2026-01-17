# telegram_backend.py
from fastapi import FastAPI, Request
from datetime import datetime, timedelta
import psycopg2
import os
import threading
import time
import requests

app = FastAPI()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")  # Postgres URL

def get_conn():
    return psycopg2.connect(DB_URL)

# ---------- Create Table ----------
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id SERIAL PRIMARY KEY,
            chat_id TEXT NOT NULL,
            username TEXT,
            message TEXT,
            send_time TIMESTAMP NOT NULL,
            status TEXT,
            repeat_type TEXT DEFAULT 'none',
            repeat_interval INT DEFAULT 1
        )
        """)
    conn.commit()

# ---------- Telegram Webhook ----------
@app.post("/telegram-webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    chat = data.get("message", {}).get("chat", {})
    chat_id = chat.get("id")
    username = chat.get("username", "")

    if chat_id:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO reminders (chat_id, username, message, send_time, status)
                    VALUES (%s, %s, %s, %s, 'added')
                    ON CONFLICT DO NOTHING
                """, (str(chat_id), username, "", datetime.now()))
            conn.commit()
    return {"ok": True}

# ---------- Schedule Reminder ----------
@app.post("/schedule-reminder")
async def schedule_reminder(req: Request):
    data = await req.json()
    chat_id = str(data["chat_id"])
    message = data["message"]
    send_time = datetime.fromisoformat(data["send_time"])
    repeat_type = data.get("repeat", "none")
    repeat_interval = int(data.get("repeat_interval", 1))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reminders (chat_id, username, message, send_time, status, repeat_type, repeat_interval)
                VALUES (%s, %s, %s, %s, 'scheduled', %s, %s)
                RETURNING id
            """, (chat_id, "", message, send_time, repeat_type, repeat_interval))
            reminder_id = cur.fetchone()[0]
        conn.commit()
    return {"status": "scheduled", "id": reminder_id}

# ---------- List Users ----------
@app.get("/list-users")
async def list_users():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT chat_id, username
                FROM reminders
                WHERE status IN ('added','scheduled','sent')
            """)
            rows = cur.fetchall()
    users = [{"chat_id": row[0], "username": row[1]} for row in rows]
    return {"users": users}

# ---------- Delete Reminder Permanently (UPDATED: delete by ID) ----------
@app.post("/delete-reminder")
async def delete_reminder(req: Request):
    data = await req.json()
    reminder_id = data.get("id")
    if not reminder_id:
        return {"status": "failed", "detail": "No id provided"}
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reminders WHERE id=%s", (reminder_id,))
        conn.commit()
    return {"status": "deleted"}

# ---------- Cancel User (stop sending future messages) ----------
@app.post("/cancel-user")
async def cancel_user(req: Request):
    data = await req.json()
    chat_id = str(data["chat_id"])
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM reminders
                WHERE chat_id=%s AND status='scheduled'
            """, (chat_id,))
        conn.commit()
    return {"status": f"user {chat_id} cancelled"}

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
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, chat_id, message, send_time, repeat_type, repeat_interval
                    FROM reminders
                    WHERE status='scheduled'
                """)
                rows = cur.fetchall()

                for id_, chat_id, message, send_time, repeat_type, repeat_interval in rows:
                    if now >= send_time:
                        success = send_telegram(chat_id, message)

                        if repeat_type != "none" and success:
                            if repeat_type == "minutes":
                                next_time = send_time + timedelta(minutes=repeat_interval)
                            elif repeat_type == "hours":
                                next_time = send_time + timedelta(hours=repeat_interval)
                            elif repeat_type == "days":
                                next_time = send_time + timedelta(days=repeat_interval)
                            elif repeat_type == "weeks":
                                next_time = send_time + timedelta(weeks=repeat_interval)
                            elif repeat_type == "months":
                                next_time = send_time + timedelta(days=30*repeat_interval)
                            else:
                                next_time = None

                            if next_time:
                                cur.execute("""
                                    UPDATE reminders SET send_time=%s, status='scheduled'
                                    WHERE id=%s
                                """, (next_time, id_))
                        else:
                            cur.execute("DELETE FROM reminders WHERE id=%s", (id_,))

            conn.commit()
        time.sleep(10)

threading.Thread(target=scheduler_loop, daemon=True).start()
