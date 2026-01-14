# smartbiz_streamlit_persistent.py
import os
import streamlit as st
import PyPDF2
from docx import Document
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("OpenAI_API_KEY")
c = OpenAI(base_url="https://openrouter.ai/api/v1",api_key=key)

# ---------- Helper Functions ----------
def extract_text(file):
    """Extract text from PDF, DOCX, or TXT files."""
    if file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(file)
        return "\n".join([page.extract_text() for page in reader.pages])
    elif file.name.endswith(".docx"):
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    elif file.name.endswith(".txt"):
        return file.read().decode("utf-8")
    return ""

def summarize_text(text, task="summary"):
    """Summarize contracts or documents using OpenAI."""
    if task == "contract":
        prompt = f"Summarize this contract and highlight key clauses, risks, and obligations:\n{text}"
    else:
        prompt = f"Summarize this document:\n{text}"
    response = client.chat.completions.create(
        model="mistralai/mixtral-8x7b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def answer_question(text, question):
    """Answer a question based on document content."""
    prompt = f"Based on the document below, answer the question:\n\n{text}\n\nQuestion: {question}"
    response = client.chat.completions.create(
        model="mistralai/mixtral-8x7b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def send_invoice_email(to_email, subject, body):
    """Send invoice or payment reminder via email."""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = os.environ.get("EMAIL_USER")
    msg['To'] = to_email
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(os.environ.get("EMAIL_USER"), os.environ.get("EMAIL_PASS"))
        server.send_message(msg)

def scrape_competitor(url):
    """Scrape product data from competitor website."""
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    products = []
    for item in soup.select(".product"):
        name = item.select_one(".name").text if item.select_one(".name") else "N/A"
        price = item.select_one(".price").text if item.select_one(".price") else "N/A"
        products.append({"Name": name, "Price": price})
    return products

# ---------- Streamlit Rerun Helper ----------
def rerun():
    """Trigger Streamlit rerun (safe for Render)."""
    from streamlit.runtime.scriptrunner import RerunException
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    raise RerunException(get_script_run_ctx())

# ---------- Initialize Session State ----------
if "contract_docs" not in st.session_state:
    st.session_state["contract_docs"] = []

if "invoices" not in st.session_state:
    st.session_state["invoices"] = []

if "competitor_data" not in st.session_state:
    st.session_state["competitor_data"] = []

if "knowledge_docs" not in st.session_state:
    st.session_state["knowledge_docs"] = []

# ---------- Streamlit UI ----------
st.set_page_config(page_title="SmartBiz AI Suite", layout="wide")
st.title("🚀 SmartBiz AI Suite")

module = st.sidebar.selectbox("Select Module", [
    "Contract Review & Summarizer",
    "Invoice Generator & Payment Reminder",
    "Web & Competitor Research",
    "Document Summarizer & Knowledge Assistant"
])

# ---------- Module 1: Contract Review ----------
if module == "Contract Review & Summarizer":
    st.header("📄 Contract Review")
    uploaded_file = st.file_uploader("Upload PDF, DOCX, or TXT contract", type=["pdf", "docx", "txt"])
    
    if uploaded_file:
        text = extract_text(uploaded_file)
        summary = summarize_text(text, task="contract")
        st.session_state.contract_docs.append({
            "filename": uploaded_file.name,
            "text": text,
            "summary": summary
        })
        rerun()  # rerun to display new entry

    for i, doc in enumerate(st.session_state.contract_docs):
        st.subheader(f"{doc['filename']}")
        st.write("**Summary:**")
        st.write(doc["summary"])
        if st.button(f"Delete {doc['filename']}", key=f"delete_contract_{i}"):
            st.session_state.contract_docs.pop(i)
            rerun()

# ---------- Module 2: Invoice Generator ----------
elif module == "Invoice Generator & Payment Reminder":
    st.header("💰 Invoice Generator")
    client_name = st.text_input("Client Name")
    client_email = st.text_input("Client Email")
    order_id = st.text_input("Order ID")
    amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)
    
    if st.button("Generate Invoice & Send Email"):
        invoice_text = f"Invoice #{order_id}\nClient: {client_name}\nAmount Due: ${amount}"
        send_invoice_email(client_email, f"Invoice #{order_id}", invoice_text)
        st.session_state.invoices.append({
            "order_id": order_id,
            "client": client_name,
            "email": client_email,
            "amount": amount,
            "text": invoice_text
        })
        rerun()
    
    for i, inv in enumerate(st.session_state.invoices):
        st.subheader(f"Invoice #{inv['order_id']} - {inv['client']}")
        st.code(inv["text"])
        if st.button(f"Delete Invoice #{inv['order_id']}", key=f"delete_invoice_{i}"):
            st.session_state.invoices.pop(i)
            rerun()

# ---------- Module 3: Competitor Research ----------
elif module == "Web & Competitor Research":
    st.header("📊 Competitor Research")
    url = st.text_input("Enter competitor product page URL")
    if st.button("Scrape Competitor Data"):
        data = scrape_competitor(url)
        st.session_state.competitor_data.append({"url": url, "data": data})
        rerun()
    
    for i, comp in enumerate(st.session_state.competitor_data):
        st.subheader(f"Competitor: {comp['url']}")
        st.table(comp["data"])
        if st.button(f"Delete Competitor Data", key=f"delete_comp_{i}"):
            st.session_state.competitor_data.pop(i)
            rerun()

# ---------- Module 4: Document Summarizer ----------
elif module == "Document Summarizer & Knowledge Assistant":
    st.header("🧠 Document Summarizer & Q&A")
    uploaded_doc = st.file_uploader("Upload PDF, DOCX, or TXT document", type=["pdf", "docx", "txt"])
    
    if uploaded_doc:
        doc_text = extract_text(uploaded_doc)
        summary = summarize_text(doc_text)
        st.session_state.knowledge_docs.append({
            "filename": uploaded_doc.name,
            "text": doc_text,
            "summary": summary,
            "question": None,
            "answer": None
        })
        rerun()

    for i, doc in enumerate(st.session_state.knowledge_docs):
        st.subheader(f"{doc['filename']}")
        st.write("**Summary:**")
        st.write(doc["summary"])
        q = st.text_input(f"Ask a question about {doc['filename']}", key=f"q_{i}")
        if st.button(f"Get Answer for {doc['filename']}", key=f"btn_{i}") and q:
            answer = answer_question(doc["text"], q)
            st.session_state.knowledge_docs[i]["question"] = q
            st.session_state.knowledge_docs[i]["answer"] = answer
            rerun()
        if doc.get("answer"):
            st.write("**Answer:**")
            st.write(doc["answer"])
        if st.button(f"Delete {doc['filename']}", key=f"delete_doc_{i}"):
            st.session_state.knowledge_docs.pop(i)
            rerun()
