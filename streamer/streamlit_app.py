# smartbiz_streamlit_ui.py
import os
import streamlit as st
import PyPDF2
from docx import Document
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import socket

load_dotenv()

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

def scrape_competitor(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        st.error(f"Failed to fetch URL: {e}")
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    products = []
    for item in soup.select(".product"):
        name = item.select_one(".name").text if item.select_one(".name") else "N/A"
        price = item.select_one(".price").text if item.select_one(".price") else "N/A"
        products.append({"Name": name, "Price": price})
    return products

# ---------- Initialize Session State ----------
if "contract_docs" not in st.session_state:
    st.session_state["contract_docs"] = []
if "invoices" not in st.session_state:
    st.session_state["invoices"] = []
if "competitor_data" not in st.session_state:
    st.session_state["competitor_data"] = []
if "knowledge_docs" not in st.session_state:
    st.session_state["knowledge_docs"] = []

# ---------- Streamlit Layout ----------
st.set_page_config(page_title="SmartBiz AI Suite", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🚀 SmartBiz AI Suite</h1>", unsafe_allow_html=True)
st.sidebar.header("Modules")

module = st.sidebar.radio("Select Module", [
    "Contract Review & Summarizer",
    "Invoice Generator & Payment Reminder",
    "Web & Competitor Research",
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

# ---------- Module 1 ----------
if module == "Contract Review & Summarizer":
    st.subheader("📄 Contract Review")
    uploaded_file = st.file_uploader("Upload PDF, DOCX, or TXT contract", type=["pdf", "docx", "txt"])
    if uploaded_file:
        text = extract_text(uploaded_file)
        summary = summarize_text(text, task="contract")
        st.session_state.contract_docs.append({"filename": uploaded_file.name, "text": text, "summary": summary})
    for i in range(len(st.session_state.contract_docs)-1, -1, -1):
        doc = st.session_state.contract_docs[i]
        with st.expander(f"{doc['filename']}"):
            st.markdown(f"**Summary:**\n{doc['summary']}")
            if st.button("Delete", key=f"delete_contract_{i}"):
                st.session_state.contract_docs.pop(i)

# ---------- Module 2: Invoice Generator & Download ----------
elif module == "Invoice Generator & Payment Reminder":
    st.subheader("💰 Invoice Generator")
    
    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("Client Name")
        client_email = st.text_input("Client Email (optional)")
    with col2:
        order_id = st.text_input("Order ID")
        amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)
    
    if st.button("Generate Invoice"):
        invoice_text = f"""
🎫 **Invoice #{order_id}**  

**Client:** {client_name}  
**Amount Due:** ${amount:.2f}  

Thank you for your business!  
"""
        st.session_state.invoices.append({
            "order_id": order_id,
            "client": client_name,
            "email": client_email,
            "amount": amount,
            "text": invoice_text
        })
        st.success(f"Invoice #{order_id} generated! ✅")
    
    for i in range(len(st.session_state.invoices)-1, -1, -1):
        inv = st.session_state.invoices[i]
        with st.expander(f"Invoice #{inv['order_id']} - {inv['client']}"):
            st.markdown(inv["text"])
            st.download_button(
                label="📥 Download Invoice",
                data=inv["text"],
                file_name=f"Invoice_{inv['order_id']}.txt",
                mime="text/plain",
                key=f"download_invoice_{i}"
            )
            if st.button("Delete Invoice", key=f"delete_invoice_{i}"):
                st.session_state.invoices.pop(i)

# ---------- Module 3 ----------
elif module == "Web & Competitor Research":
    st.subheader("📊 Competitor Research")
    url = st.text_input("Enter competitor product page URL")
    if st.button("Scrape Competitor Data"):
        data = scrape_competitor(url)
        st.session_state.competitor_data.append({"url": url, "data": data})
    for i in range(len(st.session_state.competitor_data)-1, -1, -1):
        comp = st.session_state.competitor_data[i]
        with st.expander(f"Competitor: {comp['url']}"):
            st.table(comp["data"])
            if st.button("Delete Competitor Data", key=f"delete_comp_{i}"):
                st.session_state.competitor_data.pop(i)

# ---------- Module 4 ----------
elif module == "Document Summarizer & Knowledge Assistant":
    st.subheader("🧠 Document Summarizer & Q&A")
    uploaded_doc = st.file_uploader("Upload PDF, DOCX, or TXT document", type=["pdf", "docx", "txt"])
    if uploaded_doc:
        doc_text = extract_text(uploaded_doc)
        summary = summarize_text(doc_text)
        st.session_state.knowledge_docs.append({"filename": uploaded_doc.name, "text": doc_text, "summary": summary, "question": None, "answer": None})
    for i in range(len(st.session_state.knowledge_docs)-1, -1, -1):
        doc = st.session_state.knowledge_docs[i]
        with st.expander(f"{doc['filename']}"):
            st.markdown(f"**Summary:**\n{doc['summary']}")
            q = st.text_input("Ask a question", key=f"q_{i}")
            if st.button("Get Answer", key=f"btn_{i}") and q:
                answer = answer_question(doc["text"], q)
                st.session_state.knowledge_docs[i]["question"] = q
                st.session_state.knowledge_docs[i]["answer"] = answer
            if doc.get("answer"):
                st.markdown(f"**Answer:**\n{doc['answer']}")
            if st.button("Delete Document", key=f"delete_doc_{i}"):
                st.session_state.knowledge_docs.pop(i)
