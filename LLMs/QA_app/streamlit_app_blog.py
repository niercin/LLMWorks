import streamlit as st
from pdf_qa import PdfQA
from pathlib import Path
from tempfile import NamedTemporaryFile
import time
import shutil
from constants import *

# Streamlit app code
st.set_page_config(
    page_title='Q&A Bot for PDF',
    page_icon='🔖',
    layout='wide',
    initial_sidebar_state='auto',
)

if "pdf_qa_model" not in st.session_state:
    st.session_state["pdf_qa_model"]:PdfQA = PdfQA() ## Initialisation

## To cache resource across multiple session 
@st.cache_resource
def load_llm(llm, max_len, max_new_tokens, load_in_8bit):

    if llm == LLM_OPENAI_GPT35:
        pass
    elif llm == LLM_FLAN_T5_SMALL:
        return PdfQA.create_flan_t5_small(max_len, max_new_tokens, load_in_8bit)
    elif llm == LLM_FLAN_T5_BASE:
        return PdfQA.create_flan_t5_base(max_len, max_new_tokens, load_in_8bit)
    elif llm == LLM_FLAN_T5_LARGE:
        return PdfQA.create_flan_t5_large(max_len, max_new_tokens, load_in_8bit)
    elif llm == LLM_FLAN_T5_XL:
        return PdfQA.create_flan_t5_xl(max_len, max_new_tokens, load_in_8bit)
    elif llm == LLM_FASTCHAT_T5_XL:
        return PdfQA.create_fastchat_t5_xl(max_len, max_new_tokens, load_in_8bit)
    elif llm == LLM_FALCON_SMALL:
        return PdfQA.create_falcon_instruct_small(max_len, max_new_tokens, load_in_8bit)
    else:
        raise ValueError("Invalid LLM setting")

## To cache resource across multiple session
@st.cache_resource
def load_emb(emb):
    if emb == EMB_INSTRUCTOR_XL:
        return PdfQA.create_instructor_xl()
    elif emb == EMB_SBERT_MPNET_BASE:
        return PdfQA.create_sbert_mpnet()
    elif emb == EMB_SBERT_MINILM:
        pass ##ChromaDB takes care
    else:
        raise ValueError("Invalid embedding setting")

st.title("PDF Q&A (Self hosted LLMs)")

with st.sidebar:
    txt_ext = st.radio("**Select Text Extraction**", [TEXTEXT_DEFAULT, TEXTEXT_EXTENDED], index=0)
    emb = st.radio("**Select Embedding Model**", [EMB_INSTRUCTOR_XL, EMB_SBERT_MPNET_BASE,EMB_SBERT_MINILM],index=1)
    llm = st.radio("**Select LLM Model**", [LLM_FASTCHAT_T5_XL, LLM_FLAN_T5_SMALL,LLM_FLAN_T5_BASE,LLM_FLAN_T5_LARGE,LLM_FLAN_T5_XL,LLM_FALCON_SMALL],index=2)
    load_in_8bit = st.radio("**Load 8 bit**", [True, False],index=1)
    chunk_size = st.number_input('Chunk Size', min_value=100, max_value=4096, value=100, format='%d', step=1)
    chunk_overlap = st.number_input('Chunk Overlap', min_value=0, max_value=100, value=10, format='%d', step=1)
    max_length = st.number_input('Max Length', min_value=100, max_value=4096, value=512, format='%d', step=1)
    max_new_tokens = st.number_input('Max New Tokens', min_value=100, max_value=4096, value=100, format='%d', step=1)
    pdf_file = st.file_uploader("**Upload PDF**", type="pdf")

    if st.button("Submit") and pdf_file is not None:
        with st.spinner(text="Uploading PDF and Generating Embeddings.."):
            with NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                shutil.copyfileobj(pdf_file, tmp)
                tmp_path = Path(tmp.name)
                st.session_state["pdf_qa_model"].config = {
                    "text_ext": txt_ext,
                    "pdf_path": str(tmp_path),
                    "embedding": emb,
                    "llm": llm,
                    "load_in_8bit": load_in_8bit,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap
                }
                st.session_state["pdf_qa_model"].embedding = load_emb(emb)
                st.session_state["pdf_qa_model"].llm = load_llm(llm, max_length, max_new_tokens, load_in_8bit)        
                st.session_state["pdf_qa_model"].init_embeddings()
                st.session_state["pdf_qa_model"].init_models()
                st.session_state["pdf_qa_model"].vector_db_pdf()
                st.sidebar.success("PDF uploaded successfully")

question = st.text_input('Ask a question', 'What is this document?')

if st.button("Answer"):
    try:
        st.session_state["pdf_qa_model"].retrieval_qa_chain()
        answer = st.session_state["pdf_qa_model"].answer_query(question)
        st.write(f"{answer}")
    except Exception as e:
        st.error(f"Error answering the question: {str(e)}")
