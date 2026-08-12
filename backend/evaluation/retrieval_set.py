"""Labelled retrieval questions for the seeded demo policy.

Hand-written against the six clauses in `scripts/seed.py`. Small (n=24) and
honest about it: these numbers characterise behaviour on a known corpus, they
are not a benchmark result. Every reported figure should carry its n.

Each case names the clause that *should* be retrieved. `relevant` may list more
than one where two clauses genuinely both bear on the question.

The mix is deliberate:
  * paraphrases, where a bi-encoder should do well
  * exact clause references and rare terms, where lexical search should win
  * near-miss distractors, where two clauses compete and ranking decides
"""

from dataclasses import dataclass, field


@dataclass
class RetrievalCase:
    query: str
    relevant: list[str]
    kind: str = "semantic"
    note: str = ""


# Section headers exactly as seeded.
ROOM_RENT = "4.1 ROOM RENT LIMIT"
CONSUMABLES = "4.2 NON-MEDICAL CONSUMABLES"
SURGICAL = "5.1 SURGICAL PROCEDURES"
DIAGNOSTICS = "5.4 DIAGNOSTIC INVESTIGATIONS"
PHARMACY = "6.2 PHARMACY"
DUPLICATES = "9.3 DUPLICATE AND ERRONEOUS CHARGES"
AMBULANCE = "3.4 AMBULANCE CHARGES"
COPAY = "8.1 CO-PAYMENT"
SUBLIMITS = "8.3 SUB-LIMITS ON SPECIFIED PROCEDURES"
PRE_EXISTING = "7.1 PRE-EXISTING DISEASES"
WAITING = "1.4 WAITING PERIODS"
PRE_HOSP = "2.1 PRE-HOSPITALISATION EXPENSES"
POST_HOSP = "2.2 POST-HOSPITALISATION EXPENSES"
ANAESTHETIST = "5.2 ANAESTHETIST AND SPECIALIST FEES"
IMPLANTS = "5.3 IMPLANTS AND PROSTHESES"
NURSING = "6.4 NURSING CHARGES"
DENTAL = "7.5 DENTAL TREATMENT"
DAYCARE = "3.1 DAY CARE PROCEDURES"
NOTIFICATION = "9.1 CLAIM NOTIFICATION"
FRAUD = "10.2 FRAUDULENT CLAIMS"

CASES: list[RetrievalCase] = [
    # --- paraphrase / semantic ---------------------------------------------
    RetrievalCase("How much room rent is payable per day?", [ROOM_RENT]),
    RetrievalCase("Is a private single room covered in full?", [ROOM_RENT]),
    RetrievalCase("What happens if I take a room above my eligibility?", [ROOM_RENT],
                  note="proportionate deduction lives in the room rent clause"),
    RetrievalCase("Are gloves and disposable bed sheets payable?", [CONSUMABLES]),
    RetrievalCase("Does the policy pay for attendant meals?", [CONSUMABLES]),
    RetrievalCase("Personal comfort items during hospitalisation", [CONSUMABLES]),
    RetrievalCase("Is the surgeon's fee covered for an operation?", [SURGICAL]),
    RetrievalCase("Are operation theatre charges payable?", [SURGICAL]),
    RetrievalCase("Do I need approval before a planned surgery?", [SURGICAL],
                  note="pre-authorisation is stated in the surgical clause"),
    RetrievalCase("Are blood tests and scans covered?", [DIAGNOSTICS]),
    RetrievalCase("Is a routine health screening payable?", [DIAGNOSTICS]),
    RetrievalCase("Are medicines given during admission covered?", [PHARMACY]),
    RetrievalCase("Do I need a prescription for drug charges?", [PHARMACY]),
    RetrievalCase("The hospital billed the same test twice", [DUPLICATES]),
    RetrievalCase("Can the insurer recover money already paid?", [DUPLICATES]),

    # --- lexical: exact references and rare terms ---------------------------
    RetrievalCase("clause 4.1", [ROOM_RENT], kind="lexical"),
    RetrievalCase("section 9.3", [DUPLICATES], kind="lexical"),
    RetrievalCase("anaesthetist", [SURGICAL], kind="lexical",
                  note="rare term, weak embedding signal"),
    RetrievalCase("sanitiser", [CONSUMABLES], kind="lexical"),
    RetrievalCase("radiology", [DIAGNOSTICS], kind="lexical"),
    RetrievalCase("sum insured per day", [ROOM_RENT], kind="lexical"),

    # --- distractors: two plausible clauses, ranking decides ----------------
    RetrievalCase("Room Rent - Single private room, 5 days", [ROOM_RENT], kind="distractor",
                  note="phrased as a bill line, as the auditor queries it"),
    RetrievalCase("Consumables - Surgical gloves used in theatre", [CONSUMABLES],
                  kind="distractor",
                  note="mentions surgery; must not return the surgical clause"),
    RetrievalCase("Pharmacy - Take-home medication after discharge", [PHARMACY],
                  kind="distractor",
                  note="pharmacy clause covers in-hospital only; still the right clause to read"),

    # --- clauses that compete with the six above ---------------------------
    RetrievalCase("Is the ambulance ride to hospital paid for?", [AMBULANCE]),
    RetrievalCase("How much do I have to pay myself on every claim?", [COPAY]),
    RetrievalCase("Is there a limit on cataract surgery?", [SUBLIMITS]),
    RetrievalCase("Knee replacement maximum payable", [SUBLIMITS], kind="lexical"),
    RetrievalCase("How long before a pre-existing condition is covered?", [PRE_EXISTING]),
    RetrievalCase("Illness diagnosed in the first month of the policy", [WAITING]),
    RetrievalCase("Are tests done before admission reimbursed?", [PRE_HOSP]),
    RetrievalCase("Follow-up costs after leaving hospital", [POST_HOSP]),
    RetrievalCase("Are the anaesthetist's fees covered?", [ANAESTHETIST], kind="distractor",
                  note="competes with 5.1 SURGICAL PROCEDURES"),
    RetrievalCase("Cost of a stent used in surgery", [IMPLANTS], kind="distractor",
                  note="competes with 5.1 SURGICAL PROCEDURES"),
    RetrievalCase("Private duty nurse charges", [NURSING], kind="distractor",
                  note="competes with 4.1 room tariff and 4.2 consumables"),
    RetrievalCase("Is a tooth extraction covered?", [DENTAL]),
    RetrievalCase("Treatment finished in under a day without admission", [DAYCARE]),
    RetrievalCase("When must I tell the insurer about an admission?", [NOTIFICATION],
                  kind="distractor", note="competes with 9.3, same section number prefix"),
    RetrievalCase("What happens if a claim is dishonest?", [FRAUD], kind="distractor",
                  note="competes with 9.3 duplicate and erroneous charges"),
    RetrievalCase("annexure B", [DAYCARE], kind="lexical"),
    RetrievalCase("thirty-six months of continuous coverage", [PRE_EXISTING], kind="lexical"),
    RetrievalCase("reasonable and customary charges", [ANAESTHETIST], kind="lexical"),
]
