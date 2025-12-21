# pdf.py
from pypdf import PdfReader
from docx import Document
import io

def extract_intel(file_bytes, filename):
    text = ""
    try:
        if filename.endswith('.pdf'):
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif filename.endswith('.docx'):
            doc = Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            text = file_bytes.decode('utf-8', errors='ignore')
            
        return text[:40000] # Context limit
    except Exception as e:
        return "File Error: " + str(e)
