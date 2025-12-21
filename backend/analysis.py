# analysis.py
import pandas as pd
import matplotlib.pyplot as plt
import io, base64

def process_data(file_bytes, filename):
    try:
        # Check file extension
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            df = pd.read_excel(io.BytesIO(file_bytes))
            
        plt.figure(figsize=(10, 6))
        # Plot top 15 rows of numeric data
        df.head(15).select_dtypes(include=['number']).plot(kind='bar', color='#EAB308')
        plt.title("Dynamo Analysis: " + filename)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        return {
            "image": "data:image/png;base64," + img_b64, 
            "insight": "Data trends analyzed by Dynamo AI."
        }
    except Exception as e: 
        return {"error": "Analysis Error: " + str(e)}
