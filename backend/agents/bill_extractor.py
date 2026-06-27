import pdfplumber
import json
from core.llm import groq_client

SYSTEM_PROMPT = """You are an expert medical billing extractor for Indian healthcare claims.
Extract the hospital bill into a structured JSON format.
The JSON must have this exact structure:
{
  "total_billed": 150000.0,
  "items": [
    {"category": "Room Rent", "description": "Deluxe Room 3 days", "billed_amount": 15000.0},
    {"category": "Consumables", "description": "Surgical Gloves", "billed_amount": 500.0}
  ]
}
Ensure all amounts are floats. Categorize items exactly into one of these: 'Room Rent', 'Consumables', 'Pharmacy', 'Surgeon Fees', 'Diagnostics', 'Other'.
Do NOT include any extra text, only the JSON object.
"""

async def extract_bill_data(pdf_path: str) -> dict:
    from core.llm import GROQ_API_KEY
    if not GROQ_API_KEY or GROQ_API_KEY == "":
        print("MOCKING GROQ API (No API Key found)")
        return {
            "total_billed": 150000.0,
            "items": [
                {"category": "Room Rent", "description": "Deluxe Room 3 days", "billed_amount": 15000.0},
                {"category": "Consumables", "description": "Surgical Gloves", "billed_amount": 500.0},
                {"category": "Surgeon Fees", "description": "Appendectomy", "billed_amount": 100000.0},
                {"category": "Diagnostics", "description": "Blood Test", "billed_amount": 34500.0}
            ]
        }
        
    # 1. Extract text using pdfplumber
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    
    # 2. Call Groq Llama-3 API
    response = await groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this medical bill:\n\n{text}"}
        ],
        model="llama3-70b-8192",
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    
    result_text = response.choices[0].message.content
    return json.loads(result_text)
