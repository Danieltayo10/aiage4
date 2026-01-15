# telegram_backend.py
from fastapi import FastAPI, Request
import os

app = FastAPI()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

@app.post("/telegram-webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    chat = data.get("message", {}).get("chat", {})
    chat_id = chat.get("id")
    username = chat.get("username", "")
    first_name = chat.get("first_name", "")

    if chat_id:
        # Save silently
        os.makedirs("data", exist_ok=True)
        with open("data/telegram_users.txt", "a") as f:
            f.write(f"{chat_id},{username},{first_name}\n")
    return {"ok": True}


@app.get("/telegram-webhook")
def test_get():
    return {"ok": "Webhook is running, POST messages will be accepted here."}

# Run locally for dev: uvicorn telegram_backend:app --host 0.0.0.0 --port 8001
