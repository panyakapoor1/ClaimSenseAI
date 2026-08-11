from typing import List, Dict

from core.llm import LLM_MODEL, require_llm

APPEAL_PROMPT = """You are an expert patient advocate and medical billing specialist.
Your job is to write a formal, persuasive, and professional appeal letter to a hospital or insurance company.
The patient's claim has been audited, and several line items were REJECTED or improperly billed according to the insurance policy.

### REJECTED/DISPUTED CLAIM ITEMS:
{disputed_items}

### INSTRUCTIONS:
1. Write a formal business letter addressed to the "Claims Review Department".
2. State clearly that you are appealing the rejection/charges of the specified items.
3. For each disputed item, explicitly cite the "Reason" and the "Policy Clause" to argue why the charge should be reversed or covered.
4. Maintain a professional, firm, yet polite tone.
5. Do not include placeholders like "[Your Name]", just sign off as "Patient Advocate".
6. Return the raw markdown text for the letter. DO NOT return JSON. Do not include backticks around the markdown unless they are part of the formatting.
"""

async def generate_appeal_letter(disputed_items_data: List[Dict]) -> str:
    """
    Generates a formal appeal letter using Llama-3 based on the disputed audit findings.
    """
    client = require_llm()

    if not disputed_items_data:
        return "No rejected items found to appeal."

    formatted_items = ""
    for idx, item in enumerate(disputed_items_data, 1):
        formatted_items += f"\n--- Item {idx} ---\n"
        formatted_items += f"Category: {item['category']}\n"
        formatted_items += f"Description: {item['description']}\n"
        formatted_items += f"Billed Amount: {item['billed_amount']}\n"
        formatted_items += f"Audit Status: {item['audit_status']}\n"
        formatted_items += f"Audit Reason: {item['audit_reason']}\n"
        formatted_items += f"Cited Policy Clause: {item['policy_clause']}\n"
        formatted_items += f"Clause Text: {item['clause_text']}\n"

    prompt = APPEAL_PROMPT.format(disputed_items=formatted_items)

    # Errors propagate on purpose. Returning the error text as the letter body
    # would persist a failure message into appeal_documents as if it were a
    # generated appeal, and the UI would render it as one.
    response = await client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a professional patient advocate. You output only the markdown text of the letter."},
            {"role": "user", "content": prompt}
        ],
        model=LLM_MODEL,
        temperature=0.3
    )

    return response.choices[0].message.content
