# smartbiz_streamlit_ui.py
import os
import streamlit as st
import PyPDF2
from docx import Document
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timedelta
import requests
import sqlite3

load_dotenv()

# ---------- Telegram Bot Setup ----------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_LINK = f"https://t.me/{os.getenv('TELEGRAM_BOT_USERNAME')}"

# ---------- OpenAI Setup ----------
key = os.getenv("OpenAI_API_KEY")
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

# ---------- Load Telegram chat IDs from backend DB ----------
import sqlite3
conn = sqlite3.connect("reminders.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS reminders (chat_id TEXT, message TEXT, send_time TEXT, status TEXT)")
conn.commit()
c.execute("SELECT DISTINCT chat_id FROM reminders")
rows = c.fetchall()
for row in rows:
    chat_id = row[0]
    if chat_id not in st.session_state.telegram_customers:
        st.session_state.telegram_customers.append(chat_id)
conn.close()

# ---------- Streamlit Layout ----------
st.set_page_config(page_title="SmartBiz AI Suite", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🚀 SmartBiz AI Suite</h1>", unsafe_allow_html=True)
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
    st.subheader("📲 Product Reminder via Telegram")

    # --- Onboarding Instructions ---
    st.markdown("**Step 1: Share this bot link with your customers:**")
    st.code(f"{TELEGRAM_BOT_LINK}", language="text")
    st.markdown("Customers must click **Start** once to receive messages.")

    # --- Add New Customers ---
    st.markdown("**Step 2: Add customer chat IDs** (auto-loaded from backend)")
    new_chat_id = st.text_input("Enter new customer chat ID")
    if st.button("Add Customer"):
        if new_chat_id.strip() and new_chat_id not in st.session_state.telegram_customers:
            st.session_state.telegram_customers.append(new_chat_id.strip())
            conn = sqlite3.connect("reminders.db")
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO reminders (chat_id,message,send_time,status) VALUES (?,?,?,?)",
                      (new_chat_id.strip(),"",datetime.now().isoformat(),"added"))
            conn.commit()
            conn.close()

    # --- Message Composition ---
    message = st.text_area("Type the message to send")
    send_option = st.radio("Send Time", ["Now", "Minutes", "Hours", "Days"])
    delay_value = 0
    if send_option != "Now":
        delay_value = st.number_input(f"Delay ({send_option})", min_value=1, step=1)

    if st.button("Send Reminder"):
        if send_option == "Now":
            send_time = datetime.now()
        elif send_option == "Minutes":
            send_time = datetime.now() + timedelta(minutes=delay_value)
        elif send_option == "Hours":
            send_time = datetime.now() + timedelta(hours=delay_value)
        elif send_option == "Days":
            send_time = datetime.now() + timedelta(days=delay_value)

        conn = sqlite3.connect("reminders.db")
        c = conn.cursor()
        for chat_id in st.session_state.telegram_customers:
            c.execute("INSERT INTO reminders (chat_id,message,send_time,status) VALUES (?,?,?,?)",
                      (chat_id, message, send_time.isoformat(), "scheduled"))
        conn.commit()
        conn.close()
        st.success("Reminder scheduled successfully!")

    # --- Display Reminders ---
    st.markdown("**Sent / Scheduled Reminders**")
    conn = sqlite3.connect("reminders.db")
    c = conn.cursor()
    c.execute("SELECT chat_id,message,send_time,status FROM reminders ORDER BY send_time DESC")
    rows = c.fetchall()
    conn.close()
    for i, (chat_id, msg, send_time, status) in enumerate(rows):
        with st.expander(f"{chat_id} - Status: {status}"):
            st.write(f"Message: {msg}")
            st.write(f"Scheduled Time: {send_time}")
