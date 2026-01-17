import os
import streamlit as st
import PyPDF2
from docx import Document
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timedelta
import requests

load_dotenv()

# ---------- Telegram Bot Setup ----------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_LINK = f"https://t.me/{os.getenv('TELEGRAM_BOT_USERNAME')}"
BACKEND_URL = os.getenv("TELEGRAM_BACKEND_URL")  # Backend URL for scheduling

def send_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            return f"Failed: {response.text}"
        return "Sent Successfully"
    except Exception as e:
        return f"Failed: {e}"

def schedule_telegram(chat_id, message, send_time, repeat_type="none", repeat_interval=1):
    now = datetime.now()
    if send_time <= now and repeat_type == "none":
        return send_telegram(chat_id, message)

    payload = {
        "chat_id": chat_id,
        "message": message,
        "send_time": send_time.isoformat(),
        "repeat": repeat_type,
        "repeat_interval": repeat_interval
    }

    try:
        r = requests.post(f"{BACKEND_URL}/schedule-reminder", json=payload, timeout=10)
        if r.status_code == 200:
            # Expect backend to return the reminder id
            return r.json() if r.headers.get("content-type") == "application/json" else f"Scheduled for {send_time.strftime('%Y-%m-%d %H:%M')}"
        else:
            return "Failed to schedule"
    except Exception as e:
        return f"Backend error: {e}"

def delete_reminder_backend(reminder_id):
    """Delete reminder in backend PostgreSQL by id"""
    try:
        r = requests.post(f"{BACKEND_URL}/delete-reminder", json={"id": reminder_id}, timeout=10)
        return r.json().get("status", "failed")
    except Exception as e:
        return f"Failed: {e}"

# ---------- OpenAI Setup ----------
key = os.getenv("OPENAI_API_KEY")
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)

# ---------- Helper Functions ----------
def extract_text(file):
    if file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(file)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    elif file.name.endswith(".docx"):
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    elif file.name.endswith(".txt"):
        return file.read().decode("utf-8")
    return ""

def summarize_text(text, task="summary"):
    prompt = (
        f"Summarize this contract highlighting key clauses, risks, obligations:\n{text}"
        if task == "contract"
        else f"Summarize this document:\n{text}"
    )
    response = client.chat.completions.create(
        model="mistralai/mixtral-8x7b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def answer_question(text, question):
    prompt = f"Based on the document below, answer the question:\n\n{text}\n\nQuestion: {question}"
    response = client.chat.completions.create(
        model="mistralai/mixtral-8x7b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ---------- Session State ----------
for key in ["contract_docs", "invoices", "reminders", "knowledge_docs", "telegram_customers"]:
    if key not in st.session_state:
        st.session_state[key] = []

# ---------- Load Telegram chat_ids automatically from backend ----------
try:
    resp = requests.get(f"{BACKEND_URL}/list-users", timeout=10)
    if resp.status_code == 200:
        users = resp.json().get("users", [])
        for u in users:
            chat_id = str(u["chat_id"])
            if chat_id not in st.session_state.telegram_customers:
                st.session_state.telegram_customers.append(chat_id)
except:
    pass

# ---------- Streamlit Layout ----------
st.set_page_config(page_title="SmartBiz AI Suite", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'> SmartBiz AI Suite</h1>", unsafe_allow_html=True)
st.sidebar.header("Modules")

module = st.sidebar.radio("Select Module", [
    "Contract Review & Summarizer",
    "Invoice Generator & Receipt",
    "Product Reminder Telegram",
    "Document Summarizer & Knowledge Assistant"
])

st.markdown("""
<style>
div.stButton > button {
    width: 100%;
    background-color: #4B8BBE;
    color: white;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# ---------- MODULE 3 ----------
if module == "Product Reminder Telegram":
    st.subheader(" Product Reminder via Telegram")
    
    st.markdown("**Step 1: Share this bot link with your customers:**")
    st.code(f"{TELEGRAM_BOT_LINK}", language="text")
    st.markdown("Customers must click **Start** once to receive messages.")

    st.markdown("**Step 2: Add customer chat IDs** (auto-loaded from backend)")
    new_chat_id = st.text_input("Enter new customer chat ID")
    if st.button("Add Customer"):
        if new_chat_id.strip() and new_chat_id not in st.session_state.telegram_customers:
            st.session_state.telegram_customers.append(new_chat_id.strip())

    st.markdown("**Loaded Customer Chat IDs:**")
    if st.session_state.telegram_customers:
        st.write(st.session_state.telegram_customers)
    else:
        st.write("No customers yet.")

    # --- Message Composition ---
    message = st.text_area("Type the message to send")
    send_option = st.radio("Send Time", ["Now", "Minutes", "Hours", "Days"])
    delay_value = 0
    if send_option != "Now":
        delay_value = st.number_input(f"Delay ({send_option})", min_value=1, step=1)

    repeat_type = st.selectbox("Repeat", ["none", "minutes", "hours", "days", "weeks", "months"])
    repeat_interval = 1
    if repeat_type != "none":
        repeat_interval = st.number_input("Repeat every N units", min_value=1, step=1)

    if st.button("Send Reminder"):
        if send_option == "Now":
            send_time = datetime.now()
        elif send_option == "Minutes":
            send_time = datetime.now() + timedelta(minutes=delay_value)
        elif send_option == "Hours":
            send_time = datetime.now() + timedelta(hours=delay_value)
        elif send_option == "Days":
            send_time = datetime.now() + timedelta(days=delay_value)

        for chat_id in st.session_state.telegram_customers:
            result = schedule_telegram(chat_id, message, send_time, repeat_type, repeat_interval)
            reminder_id = None
            if isinstance(result, dict) and "id" in result:
                reminder_id = result["id"]
                status = f"Scheduled for {send_time.strftime('%Y-%m-%d %H:%M')}"
            else:
                status = result
            st.session_state.reminders.append({
                "id": reminder_id,
                "chat_id": chat_id,
                "message": message,
                "time": send_time,
                "status": status
            })

    st.markdown("**Sent / Scheduled Reminders**")
    for i in range(len(st.session_state.reminders)-1, -1, -1):
        r = st.session_state.reminders[i]
        with st.expander(f"{r['chat_id']} - Status: {r['status']}"):
            st.write(f"Message: {r['message']}")
            st.write(f"Scheduled Time: {r['time']}")
            if st.button("Delete Reminder", key=f"delete_reminder_{i}"):
                if r.get("id"):
                    status = delete_reminder_backend(r["id"])
                else:
                    status = "No ID to delete"
                st.session_state.reminders.pop(i)
