#pdf.py
from pypdf import PdfReader
from docx import Document
import io

def extract_intel(file_bytes, filename):
    """
    Extracts text context from PDF, Word, or TXT files.
    """
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
            # Assume plain text
            text = file_bytes.decode('utf-8', errors='ignore')
            
        # Return truncated text to fit inside LLM context window (approx 40k chars)
        return text[:40000]
    except Exception as e:
        return f"File processing error: {str(e)}"