import asyncio
import json

import pdfplumber

from core.llm import LLM_MODEL, require_llm

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
    client = require_llm()

    # 1. Extract text using pdfplumber
    def _extract():
        t = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    t += extracted + "\n"
        return t
    text = await asyncio.to_thread(_extract)
    
    # 2. Call Groq Llama-3 API
    response = await client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this medical bill:\n\n{text}"}
        ],
        model=LLM_MODEL,
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    
    result_text = response.choices[0].message.content
    return json.loads(result_text)
