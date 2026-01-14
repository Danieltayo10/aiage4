# smartbiz_streamlit_ui.py
import os
import streamlit as st
import PyPDF2
from docx import Document
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

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
    except Exception as e:
        st.error(e)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    products = []
    for item in soup.select(".product"):
        name = item.select_one(".name").text if item.select_one(".name") else "N/A"
        price = item.select_one(".price").text if item.select_one(".price") else "N/A"
        products.append({"Name": name, "Price": price})
    return products

# ---------- Session State ----------
for key in ["contract_docs", "invoices", "competitor_data", "knowledge_docs"]:
    if key not in st.session_state:
        st.session_state[key] = []

# ---------- UI ----------
st.set_page_config(page_title="SmartBiz AI Suite", layout="wide")
st.markdown("<h1 style='text-align:center;color:#4B8BBE;'>🚀 SmartBiz AI Suite</h1>", unsafe_allow_html=True)

module = st.sidebar.radio("Select Module", [
    "Contract Review & Summarizer",
    "Invoice Generator",
    "Web & Competitor Research",
    "Document Summarizer & Knowledge Assistant"
])

# ---------- MODULE 1: CONTRACT REVIEW ----------
if module == "Contract Review & Summarizer":
    st.subheader("📄 Contract Review")

    uploaded = st.file_uploader("Upload contract", ["pdf", "docx", "txt"])
    if uploaded:
        text = extract_text(uploaded)
        summary = summarize_text(text, "contract")
        st.session_state.contract_docs.append({
            "filename": uploaded.name,
            "text": text,
            "summary": summary,
            "qa": []
        })

    for i in range(len(st.session_state.contract_docs)-1, -1, -1):
        doc = st.session_state.contract_docs[i]
        with st.expander(doc["filename"]):
            st.markdown("### Summary")
            st.markdown(doc["summary"])

            st.markdown("### Ask more questions")
            q = st.text_input("Question", key=f"contract_q_{i}")
            if st.button("Ask", key=f"contract_btn_{i}") and q:
                a = answer_question(doc["text"], q)
                doc["qa"].append({"q": q, "a": a})

            for qa in doc["qa"]:
                st.markdown(f"**Q:** {qa['q']}")
                st.markdown(f"**A:** {qa['a']}")

            if st.button("Delete", key=f"del_contract_{i}"):
                st.session_state.contract_docs.pop(i)

# ---------- MODULE 2: INVOICE / RECEIPT ----------
elif module == "Invoice Generator":
    st.subheader("🧾 Receipt Generator")

    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("Client Name")
        receipt_id = st.text_input("Receipt / Order ID")
    with col2:
        amount = st.number_input("Amount ($)", min_value=0.0)

    if st.button("Generate Receipt"):
        receipt_html = f"""
        <div style="max-width:500px;margin:auto;border-radius:12px;
        padding:24px;border:1px solid #ddd;font-family:Arial;">
        <h2 style="text-align:center;color:#4B8BBE;">Payment Receipt</h2>
        <hr>
        <p><strong>Client:</strong> {client_name}</p>
        <p><strong>Receipt #:</strong> {receipt_id}</p>
        <p><strong>Amount Paid:</strong> ${amount:.2f}</p>
        <hr>
        <p style="text-align:center;">Thank you for your business 🙏</p>
        </div>
        """

        st.session_state.invoices.append({
            "id": receipt_id,
            "client": client_name,
            "amount": amount,
            "html": receipt_html
        })

        st.success("Receipt generated!")

    for i in range(len(st.session_state.invoices)-1, -1, -1):
        inv = st.session_state.invoices[i]
        with st.expander(f"Receipt #{inv['id']}"):
            st.components.v1.html(inv["html"], height=320)
            st.download_button(
                "⬇ Download Receipt",
                inv["html"],
                file_name=f"Receipt_{inv['id']}.html",
                mime="text/html"
            )
            if st.button("Delete", key=f"del_invoice_{i}"):
                st.session_state.invoices.pop(i)

# ---------- MODULE 3 ----------
elif module == "Web & Competitor Research":
    st.subheader("📊 Competitor Research")
    url = st.text_input("Competitor URL")
    if st.button("Scrape"):
        st.session_state.competitor_data.append({
            "url": url,
            "data": scrape_competitor(url)
        })

    for i in range(len(st.session_state.competitor_data)-1, -1, -1):
        comp = st.session_state.competitor_data[i]
        with st.expander(comp["url"]):
            st.table(comp["data"])
            if st.button("Delete", key=f"del_comp_{i}"):
                st.session_state.competitor_data.pop(i)

# ---------- MODULE 4 ----------
elif module == "Document Summarizer & Knowledge Assistant":
    st.subheader("🧠 Knowledge Assistant")

    uploaded = st.file_uploader("Upload document", ["pdf", "docx", "txt"])
    if uploaded:
        text = extract_text(uploaded)
        summary = summarize_text(text)
        st.session_state.knowledge_docs.append({
            "filename": uploaded.name,
            "text": text,
            "summary": summary,
            "qa": []
        })

    for i in range(len(st.session_state.knowledge_docs)-1, -1, -1):
        doc = st.session_state.knowledge_docs[i]
        with st.expander(doc["filename"]):
            st.markdown("### Summary")
            st.markdown(doc["summary"])

            st.markdown("### Ask questions")
            q = st.text_input("Question", key=f"doc_q_{i}")
            if st.button("Ask", key=f"doc_btn_{i}") and q:
                a = answer_question(doc["text"], q)
                doc["qa"].append({"q": q, "a": a})

            for qa in doc["qa"]:
                st.markdown(f"**Q:** {qa['q']}")
                st.markdown(f"**A:** {qa['a']}")

            if st.button("Delete", key=f"del_doc_{i}"):
                st.session_state.knowledge_docs.pop(i)
