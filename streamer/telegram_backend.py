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
DATABASE_URL = os.getenv("DATABASE_URL")

# ---------------- DB ----------------
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ---------------- INIT TABLES ----------------
conn = get_conn()
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    chat_id TEXT PRIMARY KEY,
    username TEXT
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    chat_id TEXT,
    message TEXT,
    send_time TIMESTAMP,
    status TEXT,
    repeat TEXT,
    repeat_interval INTEGER
);
""")

conn.commit()
cur.close()
conn.close()

# ---------------- TELEGRAM SEND ----------------
def send_telegram(chat_id, message):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=15
        )
        return r.status_code == 200
    except:
        return False

# ---------------- NEXT TIME CALCULATOR ----------------
def compute_next(send_time, repeat, interval):
    if repeat == "minutes":
        return send_time + timedelta(minutes=interval)
    if repeat == "hours":
        return send_time + timedelta(hours=interval)
    if repeat == "days":
        return send_time + timedelta(days=interval)
    if repeat == "weeks":
        return send_time + timedelta(weeks=interval)
    if repeat == "months":
        return send_time + timedelta(days=30 * interval)
    return None

# ---------------- WEBHOOK ----------------
@app.post("/telegram-webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    chat = data.get("message", {}).get("chat", {})
    chat_id = str(chat.get("id", ""))
    username = chat.get("username", "")

    if chat_id:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (chat_id, username)
            VALUES (%s, %s)
            ON CONFLICT (chat_id) DO NOTHING
        """, (chat_id, username))
        conn.commit()
        cur.close()
        conn.close()

    return {"ok": True}

# ---------------- LIST USERS ----------------
@app.get("/list-users")
async def list_users():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT chat_id, username FROM users")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"users": rows}

# ---------------- SCHEDULE REMINDER ----------------
@app.post("/schedule-reminder")
async def schedule_reminder(req: Request):
    data = await req.json()

    chat_id = str(data["chat_id"])
    message = data["message"]
    send_time = datetime.fromisoformat(data["send_time"])

    repeat = data.get("repeat", "none")
    repeat_interval = int(data.get("repeat_interval", 1))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reminders (chat_id, message, send_time, status, repeat, repeat_interval)
        VALUES (%s, %s, %s, 'scheduled', %s, %s)
    """, (chat_id, message, send_time, repeat, repeat_interval))

    conn.commit()
    cur.close()
    conn.close()

    return {"status": "scheduled"}

# ---------------- SCHEDULER LOOP ----------------
def scheduler_loop():
    while True:
        now = datetime.utcnow()

        conn = get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT * FROM reminders
            WHERE status='scheduled'
        """)
        jobs = cur.fetchall()

        for job in jobs:
            if job["send_time"] <= now:
                ok = send_telegram(job["chat_id"], job["message"])

                if job["repeat"] and job["repeat"] != "none":
                    next_time = compute_next(
                        job["send_time"],
                        job["repeat"],
                        job["repeat_interval"]
                    )

                    cur.execute("""
                        UPDATE reminders
                        SET send_time=%s
                        WHERE id=%s
                    """, (next_time, job["id"]))
                else:
                    cur.execute("""
                        UPDATE reminders
                        SET status=%s
                        WHERE id=%s
                    """, ("sent" if ok else "failed", job["id"]))

        conn.commit()
        cur.close()
        conn.close()

        time.sleep(10)

threading.Thread(target=scheduler_loop, daemon=True).start()
