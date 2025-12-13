# ... (Previous imports)
from docx import Document # <--- NEW IMPORT

# ... (Configuration & Setup remain the same) ...

# ... (Previous Endpoints: /, /chat, /vision, /transcribe, /upload-pdf, /create-razorpay-order) ...

# --- NEW: WORD EXPORT ENDPOINT ---
@app.post("/generate-word")
async def generate_word(req: ReportRequest):
    try:
        doc = Document()
        doc.add_heading('Dynamo AI Research Report', 0)

        for msg in req.history:
            role = "User Query" if msg.role == 'user' else "Dynamo Analysis"
            doc.add_heading(role, level=2)
            # Remove Markdown bolding ** for cleaner Word output
            clean_content = msg.content.replace("**", "")
            doc.add_paragraph(clean_content)
            doc.add_paragraph("-" * 20) # Separator

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        return StreamingResponse(
            buffer, 
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
            headers={"Content-Disposition": "attachment; filename=dynamo_research.docx"}
        )
    except Exception as e:
        print(f"Word Gen Error: {e}")
        raise HTTPException(500, str(e))

# ... (Keep /generate-report PDF endpoint below this) ...
