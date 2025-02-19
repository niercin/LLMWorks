from langchain.document_loaders import PDFPlumberLoader
from langchain.document_loaders import TextLoader
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import CharacterTextSplitter, TokenTextSplitter
from transformers import pipeline
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain import HuggingFacePipeline
from langchain.embeddings import HuggingFaceInstructEmbeddings, HuggingFaceEmbeddings
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.llms import OpenAI
from constants import *
from transformers import AutoTokenizer
import torch
import os
import re
import shutil

import sys
sys.path.insert(1, '../../../t.ext2.tractor')
from pageextractor import process_pdf_file
import utils

def document_array_to_txts(texts, out_dir):
    os.makedirs(out_dir)
    for page_no, page in enumerate(texts):
        with open(out_dir / ("page_" + str(page_no).zfill(5) + ".txt"), 'w') as text_file:
            text_file.write(''.join(page.page_content))
    print('Text files are created in: ' + str(out_dir))

class PdfQA:
    def __init__(self,config:dict = {}):
        self.config = config
        self.embedding = None
        self.vectordb = None
        self.llm = None
        self.qa = None
        self.retriever = None

    # The following class methods are useful to create global GPU model instances
    # This way we don't need to reload models in an interactive app,
    # and the same model instance can be used across multiple user sessions
    @classmethod
    def create_instructor_xl(cls):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        return HuggingFaceInstructEmbeddings(model_name=EMB_INSTRUCTOR_XL, model_kwargs={"device": device})
    
    @classmethod
    def create_sbert_mpnet(cls):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        return HuggingFaceEmbeddings(model_name=EMB_SBERT_MPNET_BASE, model_kwargs={"device": device})    
    
    @classmethod
    def create_flan_t5_xxl(cls, max_len, max_new_tokens, load_in_8bit=False):
        # Local flan-t5-xxl with 8-bit quantization for inference
        # Wrap it in HF pipeline for use with LangChain
        return pipeline(
            task="text2text-generation",
            model="google/flan-t5-xxl",
            max_new_tokens=max_new_tokens,
            model_kwargs={"device_map": "auto", "load_in_8bit": load_in_8bit, "max_length": max_len, "temperature": 0.}
        )
    @classmethod
    def create_flan_t5_xl(cls, max_len, max_new_tokens, load_in_8bit=False):
        return pipeline(
            task="text2text-generation",
            model="google/flan-t5-xl",
            max_new_tokens=max_new_tokens,
            model_kwargs={"device_map": "auto", "load_in_8bit": load_in_8bit, "max_length": max_len, "temperature": 0.}
        )
    
    @classmethod
    def create_flan_t5_small(cls, max_len, max_new_tokens, load_in_8bit=False):
        # Local flan-t5-small for inference
        # Wrap it in HF pipeline for use with LangChain
        model="google/flan-t5-small"
        tokenizer = AutoTokenizer.from_pretrained(model)
        return pipeline(
            task="text2text-generation",
            model=model,
            tokenizer = tokenizer,
            max_new_tokens=max_new_tokens,
            model_kwargs={"device_map": "auto", "load_in_8bit": load_in_8bit, "max_length": max_len, "temperature": 0.}
        )
    @classmethod
    def create_flan_t5_base(cls, max_len, max_new_tokens, load_in_8bit=False):
        # Wrap it in HF pipeline for use with LangChain
        model="google/flan-t5-base"
        tokenizer = AutoTokenizer.from_pretrained(model)
        return pipeline(
            task="text2text-generation",
            model=model,
            tokenizer = tokenizer,
            max_new_tokens=max_new_tokens,
            model_kwargs={"device_map": "auto", "load_in_8bit": load_in_8bit, "max_length": max_len, "temperature": 0.}
        )
    @classmethod
    def create_flan_t5_large(cls, max_len, max_new_tokens, load_in_8bit=False):
        # Wrap it in HF pipeline for use with LangChain
        model="google/flan-t5-large"
        tokenizer = AutoTokenizer.from_pretrained(model)
        return pipeline(
            task="text2text-generation",
            model=model,
            tokenizer = tokenizer,
            max_new_tokens=max_new_tokens,
            model_kwargs={"device_map": "auto", "load_in_8bit": load_in_8bit, "max_length": max_len, "temperature": 0.}
        )
    @classmethod
    def create_fastchat_t5_xl(cls, max_len, max_new_tokens, load_in_8bit=False):
        return pipeline(
            task="text2text-generation",
            model = "lmsys/fastchat-t5-3b-v1.0",
            max_new_tokens=max_new_tokens,
            model_kwargs={"device_map": "auto", "load_in_8bit": load_in_8bit, "max_length": max_len, "temperature": 0.}
        )
    
    @classmethod
    def create_falcon_instruct_small(cls, max_len, max_new_tokens, load_in_8bit=False):
        model = "tiiuae/falcon-7b-instruct"
        tokenizer = AutoTokenizer.from_pretrained(model)
        hf_pipeline = pipeline(
                task="text-generation",
                model = model,
                tokenizer = tokenizer,
                trust_remote_code = True,
                max_new_tokens=max_new_tokens,
                model_kwargs={
                    "device_map": "auto", 
                    "load_in_8bit": load_in_8bit, 
                    "max_length": max_len, 
                    "temperature": 0.01,
                    "torch_dtype":torch.bfloat16,
                    }
            )
        return hf_pipeline
    
    def init_embeddings(self) -> None:
        # OpenAI ada embeddings API
        if self.config["embedding"] == EMB_OPENAI_ADA:
            self.embedding = OpenAIEmbeddings()
        elif self.config["embedding"] == EMB_INSTRUCTOR_XL:
            # Local INSTRUCTOR-XL embeddings
            if self.embedding is None:
                self.embedding = PdfQA.create_instructor_xl()
        elif self.config["embedding"] == EMB_SBERT_MPNET_BASE:
            ## this is for SBERT
            if self.embedding is None:
                self.embedding = PdfQA.create_sbert_mpnet()
        else:
            self.embedding = None ## DuckDb uses sbert embeddings
            # raise ValueError("Invalid config")

    def init_models(self) -> None:
        """ Initialize LLM models based on config """
        load_in_8bit = self.config.get("load_in_8bit",False)
        # OpenAI GPT 3.5 API
        if self.config["llm"] == LLM_OPENAI_GPT35:
            # OpenAI GPT 3.5 API
            pass
        elif self.config["llm"] == LLM_FLAN_T5_SMALL:
            if self.llm is None:
                self.llm = PdfQA.create_flan_t5_small(load_in_8bit=load_in_8bit)
        elif self.config["llm"] == LLM_FLAN_T5_BASE:
            if self.llm is None:
                self.llm = PdfQA.create_flan_t5_base(load_in_8bit=load_in_8bit)
        elif self.config["llm"] == LLM_FLAN_T5_LARGE:
            if self.llm is None:
                self.llm = PdfQA.create_flan_t5_large(load_in_8bit=load_in_8bit)
        elif self.config["llm"] == LLM_FLAN_T5_XL:
            if self.llm is None:
                self.llm = PdfQA.create_flan_t5_xl(load_in_8bit=load_in_8bit)
        elif self.config["llm"] == LLM_FLAN_T5_XXL:
            if self.llm is None:
                self.llm = PdfQA.create_flan_t5_xxl(load_in_8bit=load_in_8bit)
        elif self.config["llm"] == LLM_FASTCHAT_T5_XL:
            if self.llm is None:
                self.llm = PdfQA.create_fastchat_t5_xl(load_in_8bit=load_in_8bit)
        elif self.config["llm"] == LLM_FALCON_SMALL:
            if self.llm is None:
                self.llm = PdfQA.create_falcon_instruct_small(load_in_8bit=load_in_8bit)
        
        else:
            raise ValueError("Invalid config")
            
    def vector_db_pdf(self) -> None:
        """
        creates vector db for the embeddings and persists them or loads a vector db from the persist directory
        """
        pdf_path = self.config.get("pdf_path",None)
        persist_directory = self.config.get("persist_directory",None)
        if persist_directory and os.path.exists(persist_directory):
            ## Load from the persist db
            self.vectordb = Chroma(persist_directory=persist_directory, embedding_function=self.embedding)
        elif pdf_path and os.path.exists(pdf_path):
            print('Processing: ' + pdf_path)
            text_extraction_method = self.config.get("text_ext", None)
            print('Text Extraction: ' + text_extraction_method)

            if text_extraction_method == TEXTEXT_DEFAULT:
                ## 1. Extract the documents
                loader = PDFPlumberLoader(pdf_path)
                documents = loader.load()
                ## 2. Split the texts
                text_splitter = CharacterTextSplitter(chunk_size=100, chunk_overlap=0)
                texts = text_splitter.split_documents(documents)
                text_splitter = TokenTextSplitter(chunk_size=self.config.get("chunk_size", 100),
                                                  chunk_overlap=self.config.get("chunk_overlap", 10))
                texts = text_splitter.split_documents(texts)

                ## niercin DEBUGGING STUFF
                #test_out_dir = utils.get_parent_directory(pdf_path) / utils.get_filename_wo_ext(pdf_path)
                #document_array_to_txts(texts, test_out_dir)
                #########

                ## 3. Create Embeddings and add to chroma store
                ##TODO: Validate if self.embedding is not None
                self.vectordb = Chroma.from_documents(documents=texts, embedding=self.embedding, persist_directory=persist_directory)
                print('Done Processing!')
            elif text_extraction_method == TEXTEXT_EXTENDED:
                # Generate texts from the PDF and place
                # them under out_dir
                out_dir = process_pdf_file(pdf_path)
                print('Text files are created in: ' + str(out_dir))
                # Create DirectoryLoader to get texts from our_dir via TextLoader
                loader = DirectoryLoader(str(out_dir), glob="**/page_*.txt", use_multithreading=True, loader_cls=TextLoader)
                # Text splitter for creating chunks of texts with given length
                text_splitter = TokenTextSplitter(chunk_size=self.config.get("chunk_size", 100),
                                                  chunk_overlap=self.config.get("chunk_overlap", 10))
                texts = text_splitter.split_documents(loader.load())
                self.vectordb = Chroma.from_documents(documents=texts, embedding=self.embedding, persist_directory=persist_directory)
                try:
                    os.remove(pdf_path)
                    shutil.rmtree(out_dir)
                except OSError:
                    pass
                print('Done Processing!')
            else:
                raise ValueError("Unknown Text Extraction Method: " + text_extraction_method)
        else:
            raise ValueError("NO PDF found")

    def retrieval_qa_chain(self):
        """
        Creates retrieval qa chain using vectordb as retrivar and LLM to complete the prompt
        """
        ##TODO: Use custom prompt
        self.retriever = self.vectordb.as_retriever(search_kwargs={"k":3})
        
        if self.config["llm"] == LLM_OPENAI_GPT35:
          # Use ChatGPT API
          self.qa = RetrievalQA.from_chain_type(llm=OpenAI(model_name=LLM_OPENAI_GPT35, temperature=0.), chain_type="stuff",\
                                      retriever=self.vectordb.as_retriever(search_kwargs={"k":3}))
        else:
            hf_llm = HuggingFacePipeline(pipeline=self.llm,model_id=self.config["llm"])

            self.qa = RetrievalQA.from_chain_type(llm=hf_llm, chain_type="stuff",retriever=self.retriever)
            if self.config["llm"] == LLM_FLAN_T5_SMALL or self.config["llm"] == LLM_FLAN_T5_BASE or self.config["llm"] == LLM_FLAN_T5_LARGE:
                question_t5_template = """
                context: {context}
                question: {question}
                answer: 
                """
                QUESTION_T5_PROMPT = PromptTemplate(
                    template=question_t5_template, input_variables=["context", "question"]
                )
                self.qa.combine_documents_chain.llm_chain.prompt = QUESTION_T5_PROMPT
            self.qa.combine_documents_chain.verbose = True
            self.qa.return_source_documents = True
    def answer_query(self,question:str) ->str:
        """
        Answer the question
        """
        answer_dict = self.qa({"query":question,})
        print(answer_dict)
        answer = answer_dict["result"]
        if self.config["llm"] == LLM_FASTCHAT_T5_XL:
            answer = self._clean_fastchat_t5_output(answer)
        return answer
    def _clean_fastchat_t5_output(self, answer: str) -> str:
        # Remove <pad> tags, double spaces, trailing newline
        answer = re.sub(r"<pad>\s+", "", answer)
        answer = re.sub(r"  ", " ", answer)
        answer = re.sub(r"\n$", "", answer)
        return answer
