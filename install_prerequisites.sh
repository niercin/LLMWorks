#!/bin/bash

sudo apt install python3-pip

pip install langchain==0.0.189 --break-system-packages
pip install chromadb==0.3.25 --break-system-packages
pip install pdfplumber==0.9.0 --break-system-packages
pip install tiktoken==0.4.0 --break-system-packages
pip install lxml==4.9.2 --break-system-packages
pip install torch==2.0.1 --break-system-packages
pip install transformers==4.29.2 --break-system-packages
pip install accelerate==0.19.0 --break-system-packages
pip install sentence-transformers==2.2.2 --break-system-packages
pip install einops==0.6.1 --break-system-packages
pip install xformers==0.0.20 --break-system-packages

pip install streamlit --break-system-packages

