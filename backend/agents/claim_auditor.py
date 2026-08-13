import json

from core.llm import LLM_MODEL, require_llm
from models.claim import ClaimItem
from services.retrieval import search_policy

AUDIT_PROMPT = """You are an expert medical insurance claims auditor.
Your job is to determine whether a specific line item from a hospital bill should be APPROVED, CAPPED, REJECTED or sent for review, based STRICTLY on the provided insurance policy clauses.

### CLAIM ITEM TO AUDIT:
- Category: {category}
- Description: {description}
- Billed Amount: {billed_amount}

### RELEVANT POLICY CLAUSES:
{policy_clauses}

### INSTRUCTIONS:
1. Review the policy clauses carefully to see if the item is explicitly excluded, capped, or allowed.
2. If the item is explicitly excluded, mark it REJECTED.
3. If the item is covered but subject to a limit the billed amount exceeds, mark it
   CAPPED and set "capped_amount" to the maximum the policy allows.
4. If the item is covered without limit, mark it APPROVED.
5. If the clauses do not mention the item at all, mark it NEEDS_REVIEW. Do not
   assume medical necessity. Say that the policy is silent and a human must decide.
6. Set "clause_ref" to the number shown in brackets beside the clause you relied on,
   for example 2 for "[Clause 2]". Use null when no clause applied.
7. Provide a confidence score between 0.0 and 1.0 reflecting how directly the
   clauses settle the question.

Respond strictly in the following JSON schema:
{{
  "status": "APPROVED" | "CAPPED" | "REJECTED" | "NEEDS_REVIEW",
  "reason": "Explain your reasoning based on the policy text.",
  "clause_ref": 2,
  "policy_clause_cited": "The exact 'Header' you relied on. Leave null if none applied.",
  "original_clause_text": "A brief snippet of the text you relied on. Leave null if none applied.",
  "page_number": "The page number of the cited clause. Leave null if none applied.",
  "capped_amount": 12000.0,
  "confidence": 0.95
}}
"""


async def audit_claim_item(item: ClaimItem, policy_id: str) -> dict:
    """Adjudicate one line item against the clauses retrieved for it.

    Returns the model's verdict plus `chunk_id`: the database id of the passage
    it said it relied on. That link is what turns a quoted clause into something
    a reviewer can open, and what makes a fabricated citation detectable, since
    a clause_ref outside the retrieved set resolves to nothing.
    """
    client = require_llm()

    query = f"{item.category} - {item.description}"
    candidates = await search_policy(policy_id=policy_id, query=query, top_k=5)

    formatted = ""
    for index, candidate in enumerate(candidates, start=1):
        formatted += f"\n--- [Clause {index}] ---\n"
        formatted += f"Header: {candidate.section_header} (Page {candidate.page_number})\n"
        formatted += f"Text: {candidate.text_content}\n"

    if not formatted:
        formatted = "No policy clauses were retrieved for this item."

    prompt = AUDIT_PROMPT.format(
        category=item.category,
        description=item.description,
        billed_amount=item.billed_amount,
        policy_clauses=formatted,
    )

    response = await client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You output JSON and nothing else."},
            {"role": "user", "content": prompt},
        ],
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    try:
        result = json.loads(response.choices[0].message.content)
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
            "chunk_id": None,
            "confidence": 0.0,
        }

    # Resolve the cited clause back to the passage it came from. Anything outside
    # the retrieved set is dropped rather than trusted.
    cited = None
    reference = result.get("clause_ref")
    if isinstance(reference, int) and 1 <= reference <= len(candidates):
        cited = candidates[reference - 1]

    result["chunk_id"] = cited.id if cited else None
    if cited:
        # Prefer the stored passage's own header, page and text over the model's
        # restatement of them: the record should quote the source, not a paraphrase.
        result["policy_clause_cited"] = cited.section_header
        result["page_number"] = cited.page_number
        result["original_clause_text"] = cited.text_content[:2000]
        result["retrieval"] = cited.provenance()

    return result
