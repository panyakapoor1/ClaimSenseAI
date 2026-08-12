import json

from core.llm import LLM_MODEL, require_llm

SYSTEM_PROMPT = """You are an expert medical billing extractor for Indian healthcare claims.
Extract the hospital bill into a structured JSON format.
The JSON must have this exact structure:
{
  "total_billed": 150000.0,
  "provider_name": "Sunrise Multispeciality Hospital",
  "claimant_name": "Ananya Rao",
  "admission_date": "2026-07-12",
  "discharge_date": "2026-07-15",
  "items": [
    {"category": "Room Rent", "description": "Deluxe Room 3 days", "billed_amount": 15000.0,
     "procedure_code": null, "service_date": "2026-07-12", "quantity": 3, "unit_price": 5000.0}
  ]
}
Rules:
- Copy `description` verbatim from the bill. Do not paraphrase, expand abbreviations
  or tidy the wording: the exact string is used to locate the line on the page.
- All amounts are floats without currency symbols or thousands separators.
- Dates are ISO format (YYYY-MM-DD). Use null when a date is not printed.
- Categorise each item as exactly one of: 'Room Rent', 'Consumables', 'Pharmacy',
  'Surgeon Fees', 'Diagnostics', 'Other'.
- Use null for any field the bill does not state. Never invent a value.
Return only the JSON object.
"""


async def extract_bill_data(document_text: str) -> dict:
    """Extract structured line items from already-parsed bill text.

    Takes text rather than a path: parsing (including OCR) now happens once in
    the document pipeline, and this agent works from its output. That keeps the
    OCR fallback in one place instead of duplicating it per consumer.
    """
    client = require_llm()

    response = await client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this medical bill:\n\n{document_text}"},
        ],
        model=LLM_MODEL,
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)
