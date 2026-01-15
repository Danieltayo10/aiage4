# telegram_backend.py
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ---------- Load environment ----------
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ---------- FastAPI app ----------
app = FastAPI(title="Telegram Backend for SmartBiz AI Suite")

# ---------- Ensure data folder exists ----------
os.makedirs("data", exist_ok=True)
USERS_FILE = "data/telegram_users.txt"

# ---------- Webhook route ----------
@app.post("/telegram-webhook")
async def telegram_webhook(req: Request):
    """
    Receives updates from Telegram when a user clicks /start.
    Automatically saves chat_id, username, first_name.
    """
    try:
        data = await req.json()
        chat = data.get("message", {}).get("chat", {})
        chat_id = chat.get("id")
        username = chat.get("username", "")
        first_name = chat.get("first_name", "")

        if chat_id:
            # Append to users file only if not already saved
            existing_ids = set()
            if os.path.exists(USERS_FILE):
                with open(USERS_FILE, "r") as f:
                    existing_ids = set(line.strip().split(",")[0] for line in f.readlines())

            if str(chat_id) not in existing_ids:
                with open(USERS_FILE, "a") as f:
                    f.write(f"{chat_id},{username},{first_name}\n")

                # Log for Render Free Plan visibility
                print(f"[NEW USER] chat_id: {chat_id}, username: {username}, first_name: {first_name}")
            else:
                print(f"[EXISTING USER] chat_id: {chat_id}")

        return JSONResponse(content={"ok": True})

    except Exception as e:
        print(f"[ERROR] {e}")
        return JSONResponse(content={"ok": False, "error": str(e)}, status_code=500)


# ---------- Optional health check ----------
@app.get("/health")
async def health():
    return JSONResponse(content={"status": "ok"})
