# smartbiz_streamlit_ui.py
import os
import streamlit as st
import PyPDF2
from docx import Document
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

# ---------- Twilio Setup ----------
from twilio.rest import Client as TwilioClient

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
twilio_client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)

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

def schedule_sms(phone, message, send_time):
    """
    Schedule SMS via Twilio: if send_time <= now, send immediately; else mark as scheduled
    """
    now = datetime.now()
    if send_time <= now:
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_NUMBER,
            to=phone
        )
        return "Sent Now"
    else:
        return f"Scheduled for {send_time.strftime('%Y-%m-%d %H:%M')}"

# ---------- Session State ----------
for key in ["contract_docs", "invoices", "product_reminders", "knowledge_docs"]:
    if key not in st.session_state:
        st.session_state[key] = []

# ---------- Streamlit Layout ----------
st.set_page_config(page_title="SmartBiz AI Suite", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🚀 SmartBiz AI Suite</h1>", unsafe_allow_html=True)
st.sidebar.header("Modules")

module = st.sidebar.radio("Select Module", [
    "Contract Review & Summarizer",
    "Invoice Generator & Payment Reminder",
    "Product Availability Reminders",
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

# ---------- MODULE 1: Contract Review ----------
if module == "Contract Review & Summarizer":
    st.subheader("📄 Contract Review")
    uploaded_file = st.file_uploader("Upload PDF, DOCX, or TXT contract", type=["pdf", "docx", "txt"])
    if uploaded_file:
        text = extract_text(uploaded_file)
        summary = summarize_text(text, task="contract")
        st.session_state.contract_docs.append({"filename": uploaded_file.name, "text": text, "summary": summary, "qa": []})
    for i in range(len(st.session_state.contract_docs)-1, -1, -1):
        doc = st.session_state.contract_docs[i]
        with st.expander(f"{doc['filename']}"):
            st.markdown(f"**Summary:**\n{doc['summary']}")
            q = st.text_input("Ask another question", key=f"contract_q_{i}")
            if st.button("Ask", key=f"contract_btn_{i}") and q:
                answer = answer_question(doc["text"], q)
                doc["qa"].append((q, answer))
            for q, ans in doc["qa"]:
                st.markdown(f"**Q:** {q}")
                st.markdown(f"**A:** {ans}")
            if st.button("Delete", key=f"delete_contract_{i}"):
                st.session_state.contract_docs.pop(i)

# ---------- MODULE 2: Invoice Generator ----------
elif module == "Invoice Generator & Payment Reminder":
    st.subheader("🧾 Professional Invoice Generator")

    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("Client Name")
    with col2:
        order_id = st.text_input("Invoice / Receipt Number")
        amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)

    if st.button("Generate Invoice"):
        # Professional HTML invoice
        invoice_html = f"""
        <div style="max-width:650px;margin:auto;padding:30px;border-radius:15px;
        border:2px solid #4B8BBE;font-family:Arial,sans-serif;background:#f9f9f9">
        <h1 style="text-align:center;color:#4B8BBE;">💼 Invoice</h1>
        <hr>
        <p><strong>Invoice #: </strong>{order_id}</p>
        <p><strong>Client: </strong>{client_name}</p>
        <p><strong>Amount Due: </strong>${amount:.2f}</p>
        <hr>
        <p style="text-align:center;font-size:1.1em;">Thank you for your business! 💙</p>
        </div>
        """
        st.session_state.invoices.append({
            "order_id": order_id,
            "client": client_name,
            "amount": amount,
            "html": invoice_html
        })

    for i in range(len(st.session_state.invoices)-1, -1, -1):
        inv = st.session_state.invoices[i]
        with st.expander(f"Invoice #{inv['order_id']} - {inv['client']}"):
            st.markdown(inv["html"], unsafe_allow_html=True)
            st.download_button(
                label="📥 Download Invoice",
                data=inv["html"],
                file_name=f"Invoice_{inv['order_id']}.html",
                mime="text/html",
                key=f"download_invoice_{i}"
            )
            if st.button("Delete Invoice", key=f"delete_invoice_{i}"):
                st.session_state.invoices.pop(i)

# ---------- MODULE 3: Product Availability Reminders ----------
elif module == "Product Availability Reminders":
    st.subheader("📲 Product Availability Reminder")

    products_input = st.text_input("Product(s) (comma-separated)")
    clients_input = st.text_input("Client Phone Numbers (comma-separated, with country code)")
    message_input = st.text_area("Custom Message to Send", value="Your product(s) will be available soon!")
    
    schedule_option = st.radio("Send Message", ["Now", "In X Minutes"])
    minutes_input = st.number_input("Minutes from now (if not Now)", min_value=1, step=1, value=5)

    if st.button("Schedule Reminder"):
        send_time = datetime.now()
        if schedule_option != "Now":
            send_time += timedelta(minutes=minutes_input)

        products = [x.strip() for x in products_input.split(",") if x.strip()]
        clients = [x.strip() for x in clients_input.split(",") if x.strip()]

        for phone in clients:
            msg = message_input.replace("{products}", ", ".join(products))
            status = schedule_sms(phone, msg, send_time)
            st.session_state.product_reminders.append({
                "products": products,
                "phone": phone,
                "time": send_time,
                "message": msg,
                "status": status
            })

    for i in range(len(st.session_state.product_reminders)-1, -1, -1):
        r = st.session_state.product_reminders[i]
        with st.expander(f"{r['phone']} - {', '.join(r['products'])}"):
            st.write(f"📦 Products: {', '.join(r['products'])}")
            st.write(f"📱 Phone: {r['phone']}")
            st.write(f"⏰ Scheduled Time: {r['time']}")
            st.write(f"💬 Message: {r['message']}")
            st.write(f"⚡ Status: {r['status']}")
            if st.button("Delete Reminder", key=f"delete_reminder_{i}"):
                st.session_state.product_reminders.pop(i)

# ---------- MODULE 4: Document Summarizer ----------
elif module == "Document Summarizer & Knowledge Assistant":
    st.subheader("🧠 Document Summarizer & Q&A")
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
