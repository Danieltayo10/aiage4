# smartbiz_streamlit_ui.py
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

def send_telegram(chat_id, message):
    """Send a Telegram message immediately."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            return f"Failed: {response.text}"
        return "Sent Successfully"
    except Exception as e:
        return f"Failed: {e}"

def schedule_telegram(chat_id, message, send_time):
    """Schedule Telegram messages. If send_time <= now, send immediately."""
    now = datetime.now()
    if send_time <= now:
        return send_telegram(chat_id, message)
    else:
        return f"Scheduled for {send_time.strftime('%Y-%m-%d %H:%M')}"

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

# ---------- MODULE 1 ----------
if module == "Contract Review & Summarizer":
    st.subheader("📄 Contract Review")
    uploaded_file = st.file_uploader("Upload contract", type=["pdf", "docx", "txt"])
    if uploaded_file:
        text = extract_text(uploaded_file)
        summary = summarize_text(text, task="contract")
        st.session_state.contract_docs.append({"filename": uploaded_file.name, "text": text, "summary": summary, "qa": []})
    for i in range(len(st.session_state.contract_docs)-1, -1, -1):
        doc = st.session_state.contract_docs[i]
        with st.expander(f"{doc['filename']}"):
            st.markdown(f"**Summary:**\n{doc['summary']}")
            q = st.text_input("Ask a follow-up question", key=f"contract_q_{i}")
            if st.button("Ask", key=f"contract_btn_{i}") and q:
                ans = answer_question(doc["text"], q)
                doc["qa"].append((q, ans))
            for q, ans in doc["qa"]:
                st.markdown(f"**Q:** {q}")
                st.markdown(f"**A:** {ans}")
            if st.button("Delete", key=f"delete_contract_{i}"):
                st.session_state.contract_docs.pop(i)

# ---------- MODULE 2 ----------
elif module == "Invoice Generator & Receipt":
    st.subheader("🧾 Professional Invoice Generator")
    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("Client Name")
        client_email = st.text_input("Client Email (Optional)")
    with col2:
        order_id = st.text_input("Invoice Number")
        amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)

    if st.button("Generate Invoice"):
        receipt_html = f"""
        <div style="max-width:700px;margin:auto;padding:25px;
        border-radius:12px;border:2px solid #4B8BBE;font-family:Arial;background-color:#f5f7fa">
            <h2 style="text-align:center;color:#4B8BBE;">INVOICE</h2>
            <p><strong>Invoice #:</strong> {order_id}</p>
            <p><strong>Client:</strong> {client_name}</p>
            <p><strong>Amount Due:</strong> <span style="color:green;font-weight:bold;">${amount:.2f}</span></p>
            <hr>
            <p style="text-align:center;">Thank you for your business! 💙</p>
        </div>
        """
        st.session_state.invoices.append({
            "order_id": order_id,
            "client": client_name,
            "amount": amount,
            "html": receipt_html
        })

    for i in range(len(st.session_state.invoices)-1, -1, -1):
        inv = st.session_state.invoices[i]
        with st.expander(f"Invoice #{inv['order_id']} - {inv['client']}"):
            st.markdown(inv["html"], unsafe_allow_html=True)
            st.download_button(
                "📥 Download Invoice",
                inv["html"],
                file_name=f"Invoice_{inv['order_id']}.html",
                mime="text/html",
                key=f"download_invoice_{i}"
            )
            if st.button("Delete Invoice", key=f"delete_invoice_{i}"):
                st.session_state.invoices.pop(i)

# ---------- MODULE 3 ----------
elif module == "Product Reminder Telegram":
    st.subheader("📲 Product Reminder via Telegram")
    
    # --- Onboarding Instructions ---
    st.markdown("**Step 1: Share this bot link with your customers:**")
    st.code(f"{TELEGRAM_BOT_LINK}", language="text")
    st.markdown("Customers must click **Start** once to receive messages.")

    # --- Add New Customers ---
    st.markdown("**Step 2: Add customer chat IDs**")
    new_chat_id = st.text_input("Enter new customer chat ID")
    if st.button("Add Customer"):
        if new_chat_id.strip() and new_chat_id not in st.session_state.telegram_customers:
            st.session_state.telegram_customers.append(new_chat_id.strip())

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

        for chat_id in st.session_state.telegram_customers:
            status = schedule_telegram(chat_id, message, send_time)
            st.session_state.reminders.append({
                "chat_id": chat_id,
                "message": message,
                "time": send_time,
                "status": status
            })

    # --- Display Reminders ---
    st.markdown("**Sent / Scheduled Reminders**")
    for i in range(len(st.session_state.reminders)-1, -1, -1):
        r = st.session_state.reminders[i]
        with st.expander(f"{r['chat_id']} - Status: {r['status']}"):
            st.write(f"Message: {r['message']}")
            st.write(f"Scheduled Time: {r['time']}")
            if st.button("Delete Reminder", key=f"delete_reminder_{i}"):
                st.session_state.reminders.pop(i)

# ---------- MODULE 4 ----------
elif module == "Document Summarizer & Knowledge Assistant":
    st.subheader("🧠 Document Q&A")
    uploaded_doc = st.file_uploader("Upload PDF, DOCX, or TXT document", type=["pdf", "docx", "txt"])
    if uploaded_doc:
        doc_text = extract_text(uploaded_doc)
        summary = summarize_text(doc_text)
        st.session_state.knowledge_docs.append({"filename": uploaded_doc.name, "text": doc_text, "summary": summary, "qa": []})
    for i in range(len(st.session_state.knowledge_docs)-1, -1, -1):
        doc = st.session_state.knowledge_docs[i]
        with st.expander(f"{doc['filename']}"):
            st.markdown(f"**Summary:**\n{doc['summary']}")
            q = st.text_input("Ask another question", key=f"doc_q_{i}")
            if st.button("Ask", key=f"doc_btn_{i}") and q:
                ans = answer_question(doc["text"], q)
                doc["qa"].append((q, ans))
            for q, ans in doc["qa"]:
                st.markdown(f"**Q:** {q}")
                st.markdown(f"**A:** {ans}")
            if st.button("Delete Document", key=f"delete_doc_{i}"):
                st.session_state.knowledge_docs.pop(i)

