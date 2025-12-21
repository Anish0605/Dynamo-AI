#analysis.py
import pandas as pd
import matplotlib.pyplot as plt
import io, base64

def process_data(file_bytes, filename):
    try:
        df = pd.read_csv(io.BytesIO(file_bytes)) if filename.endswith('.csv') else pd.read_excel(io.BytesIO(file_bytes))
        plt.figure(figsize=(10, 6))
        df.head(15).select_dtypes(include=['number']).plot(kind='bar', color='#EAB308')
        plt.tight_layout()
        buf = io.BytesIO(); plt.savefig(buf, format='png'); buf.seek(0); plt.close()
        return {"image": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}", "insight": "Data trends visualized."}
    except Exception as e: return {"error": str(e)}
