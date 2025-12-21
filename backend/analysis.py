# analysis.py - The Combined Intelligence Engine
import pandas as pd
import matplotlib.pyplot as plt
import io, base64
from pypdf import PdfReader
from docx import Document
import google.generativeai as genai
import config

def process_file_universally(file_bytes, filename):
    fn = filename.lower()
    try:
        # 1. TABULAR (Excel/CSV)
        if fn.endswith(('.csv', '.xlsx', '.xls')):
            df = pd.read_csv(io.BytesIO(file_bytes)) if fn.endswith('.csv') else pd.read_excel(io.BytesIO(file_bytes))
            plt.figure(figsize=(10, 5))
            numeric_df = df.select_dtypes(include=['number'])
            if not numeric_df.empty:
                numeric_df.head(10).plot(kind='bar', color='#EAB308')
                plt.title(f"Dynamo Analysis: {filename}")
                plt.tight_layout()
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                img_b64 = base64.b64encode(buf.getvalue()).decode()
                plt.close()
                return {
                    "type": "chart",
                    "image": "data:image/png;base64," + img_b64, 
                    "content": f"Data Preview:\n{df.head(5).to_markdown()}",
                    "insight": f"Extracted trends from {filename}."
                }
            return {"type": "text", "content": f"Processed {filename}.\n{df.head(10).to_markdown()}"}

        # 2. DOCUMENTS (PDF/Word)
        elif fn.endswith(('.pdf', '.docx', '.txt')):
            text = ""
            if fn.endswith('.pdf'):
                reader = PdfReader(io.BytesIO(file_bytes))
                for page in reader.pages: text += page.extract_text() + "\n"
            elif fn.endswith('.docx'):
                doc = Document(io.BytesIO(file_bytes))
                for para in doc.paragraphs: text += para.text + "\n"
            else: text = file_bytes.decode('utf-8', errors='ignore')
            return {"type": "text", "content": text[:30000], "insight": f"Read {filename} successfully."}

        # 3. VISION (Images)
        elif fn.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            gen_model = genai.GenerativeModel("gemini-2.0-flash")
            img_data = base64.b64encode(file_bytes).decode()
            image_part = {"inline_data": {"mime_type": "image/png", "data": img_data}}
            res = gen_model.generate_content(["Describe this for research purposes.", image_part])
            return {"type": "vision", "content": res.text, "image": "data:image/png;base64," + img_data, "insight": "Visual analysis complete."}

    except Exception as e:
        return {"error": str(e)}
    return {"error": "Unsupported format."}
