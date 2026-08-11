import json

from core.llm import LLM_MODEL, require_llm
from agents.rag_retriever import search_policy_chunks
from models.claim import ClaimItem

AUDIT_PROMPT = """You are an expert medical insurance claims auditor.
Your job is to determine whether a specific line item from a hospital bill should be APPROVED or REJECTED based STRICTLY on the provided insurance policy clauses.

### CLAIM ITEM TO AUDIT:
- Category: {category}
- Description: {description}
- Billed Amount: {billed_amount}

### RELEVANT POLICY CLAUSES:
{policy_clauses}

### INSTRUCTIONS:
1. Review the policy clauses carefully to see if the item is explicitly excluded, capped, or allowed.
2. If the item is excluded, mark it REJECTED.
3. If the item is covered but capped, or fully covered, mark it APPROVED (for now we treat partial as APPROVED with a reason).
4. If there is no mention of the item in the clauses, assume standard medical necessity and mark it APPROVED, but state that it relies on medical necessity.
5. Provide a confidence score between 0.0 and 1.0.

Respond strictly in the following JSON schema:
{{
  "status": "APPROVED" | "REJECTED",
  "reason": "Explain your reasoning based on the policy text.",
  "policy_clause_cited": "The exact 'section_header' you relied on. Leave null if none applied.",
  "original_clause_text": "A brief snippet of the text you relied on. Leave null if none applied.",
  "page_number": "The page number of the cited clause. Leave null if none applied.",
  "confidence": 0.95
}}
"""

async def audit_claim_item(item: ClaimItem, policy_id: str) -> dict:
    """
    Audits a single claim item by fetching relevant RAG context and querying Groq.
    """
    client = require_llm()

    # 1. Fetch relevant clauses using RAG
    query = f"{item.category} - {item.description}"
    rag_results = await search_policy_chunks(query=query, policy_id=policy_id, top_k=3)

    # 2. Format policy clauses for the prompt
    formatted_clauses = ""
    for idx, res in enumerate(rag_results, 1):
        formatted_clauses += f"\n--- Clause {idx} ---\n"
        formatted_clauses += f"Header: {res['section_header']} (Page {res['page_number']})\n"
        formatted_clauses += f"Text: {res['text_content']}\n"
    
    if not formatted_clauses:
        formatted_clauses = "No relevant policy clauses found for this item."

    # 3. Construct prompt
    prompt = AUDIT_PROMPT.format(
        category=item.category,
        description=item.description,
        billed_amount=item.billed_amount,
        policy_clauses=formatted_clauses
    )

    # 4. Call Groq
    response = await client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You output JSON and nothing else."},
            {"role": "user", "content": prompt}
        ],
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        temperature=0.1
    )

    # 5. Parse and return JSON
    try:
        content = response.choices[0].message.content
        audit_result = json.loads(content)
        return audit_result
    except Exception as e:
        # Never fall back to APPROVED here. An unparseable response means the item
        # was not adjudicated at all, and recording it as approved would put a
        # verdict in the findings table that no model ever reached.
        print(f"Error parsing Groq output for item {item.id}: {e}")
        return {
            "status": "NEEDS_REVIEW",
            "reason": "The auditor's response could not be parsed, so this item was not adjudicated. It requires manual review.",
            "policy_clause_cited": None,
            "original_clause_text": None,
            "page_number": None,
            "confidence": 0.0
        }
