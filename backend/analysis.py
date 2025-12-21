#analysis.py
import pandas as pd
import matplotlib.pyplot as plt
import io, base64

def process_data(file_bytes, filename):
    """
    Analyzes Excel/CSV files and returns a bar chart visualization.
    """
    try:
        df = pd.read_csv(io.BytesIO(file_bytes)) if filename.endswith('.csv') else pd.read_excel(io.BytesIO(file_bytes))
        
        plt.figure(figsize=(10, 6))
        # Select numeric columns only for the bar chart
        df.head(15).select_dtypes(include=['number']).plot(kind='bar', color='#EAB308')
        plt.title(f"Dynamo Analysis: {filename}")
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        return {"image": f"data:image/png;base64,{img_b64}", "insight": "Data trends visualized by Dynamo."}
    except Exception as e: 
        return {"error": f"Analysis Error: {str(e)}"}