"""Deterministic demo data, produced by running the real pipeline.

Nothing analytical is written by hand. The script authors the two things a real
tenant would supply — a policy document and four hospital bills — renders them as
actual PDFs, stores them, and then runs the same ingestion, retrieval,
adjudication and risk scoring the application runs for an uploaded claim.

So the verdicts, the cited clauses, the located regions and the risk signals in
the demo are all genuinely computed. An earlier version of this script inserted
them directly, which meant the demo displayed a decomposed risk score that no
engine had ever produced.

Without GROQ_API_KEY the adjudication step cannot run. The script still creates
the documents, parses them, and computes the deterministic risk signals, and
leaves the claims visibly un-adjudicated rather than filling in verdicts.

    docker compose run --rm fastapi python scripts/seed.py
"""

import asyncio
import datetime
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select

from core.bootstrap import ensure_demo_tenant
from core.database import AsyncSessionLocal
from core.llm import LLM_AVAILABLE
from core.pdf_builder import text_layer_pdf
from models import (
    Claim,
    Claimant,
    ClaimStatus,
    Document,
    DocumentKind,
    Policy,
    Provider,
)
from services import storage
from tasks.audit_claim import audit_claim_task
from tasks.extract_bill import extract_bill_task
from tasks.ingest_policy import ingest_policy_task

NS = uuid.UUID("6f1a9d2c-4b7e-4c31-9f80-2a6d5e0b7c14")


def sid(name: str) -> uuid.UUID:
    return uuid.uuid5(NS, name)


# ---------------------------------------------------------------------------
# The policy document
# ---------------------------------------------------------------------------

POLICY_CLAUSES = [
    ("1.1 DEFINITIONS",
     "In this policy, 'Insured Person' means the individual named in the schedule. "
     "'Hospital' means an institution registered with the local authorities having at "
     "least ten inpatient beds, qualified nursing staff on duty at all times, and a "
     "fully equipped operation theatre."),
    ("1.4 WAITING PERIODS",
     "Expenses related to the treatment of any illness diagnosed within thirty days of "
     "the first policy commencement date are not payable, other than claims arising "
     "from accidental injury."),
    ("2.1 PRE-HOSPITALISATION EXPENSES",
     "Medical expenses incurred in the sixty days immediately before the date of "
     "admission are payable, provided they relate to the same condition for which "
     "hospitalisation was required and the inpatient claim has been admitted."),
    ("2.2 POST-HOSPITALISATION EXPENSES",
     "Medical expenses incurred in the ninety days immediately following discharge are "
     "payable where they relate directly to the condition treated during the admission, "
     "subject to the sum insured."),
    ("3.1 DAY CARE PROCEDURES",
     "Procedures listed in Annexure B which require less than twenty-four hours of "
     "hospitalisation due to technological advancement are covered. Outpatient treatment "
     "not requiring admission is not covered under this section."),
    ("3.4 AMBULANCE CHARGES",
     "Road ambulance charges for transporting the insured person to hospital are "
     "reimbursed up to 2,000 rupees per hospitalisation, provided the admission is an "
     "admissible claim under this policy."),
    ("4.1 ROOM RENT LIMIT",
     "Room rent is payable up to 1% of the sum insured per day for a shared room and 2% "
     "for a single private room. Charges in excess of this limit are borne by the "
     "insured. Proportionate deduction applies to associated medical expenses where the "
     "room category exceeds the eligible limit."),
    ("4.2 NON-MEDICAL CONSUMABLES",
     "Items of personal comfort and convenience, including but not limited to gloves, "
     "sanitiser, disposable bed sheets, attendant meals and toiletries, are excluded "
     "from coverage and are not payable under this policy."),
    ("5.1 SURGICAL PROCEDURES",
     "Surgeon fees, anaesthetist fees and operation theatre charges for medically "
     "necessary surgical procedures are covered in full, subject to the sum insured and "
     "to pre-authorisation where the procedure is planned."),
    ("5.2 ANAESTHETIST AND SPECIALIST FEES",
     "Fees charged by the anaesthetist, specialist consultants and the operating team in "
     "respect of a covered surgical procedure are payable at actuals, subject to "
     "reasonable and customary charges for the geography."),
    ("5.3 IMPLANTS AND PROSTHESES",
     "The cost of implants, stents and prostheses used during a covered surgical "
     "procedure is payable where supported by the invoice and the batch record. Cosmetic "
     "implants are excluded."),
    ("5.4 DIAGNOSTIC INVESTIGATIONS",
     "Pathology and radiology investigations directly related to the admitted condition "
     "are covered. Routine screening not connected to the diagnosis is not payable."),
    ("5.5 SECOND OPINION",
     "Charges for a second medical opinion obtained at the insured person's own "
     "initiative are not payable unless the insurer requested the opinion in writing."),
    ("6.1 CONSULTATION CHARGES",
     "Charges for consultations by the treating physician during the period of "
     "hospitalisation are covered. Consultations unrelated to the admitted condition are "
     "not payable."),
    ("6.2 PHARMACY",
     "Drugs and consumables prescribed by the treating physician during the period of "
     "hospitalisation are covered when supported by a valid prescription."),
    ("6.4 NURSING CHARGES",
     "General nursing charges forming part of the room tariff are covered. Charges for a "
     "private duty nurse engaged at the request of the insured person or the family are "
     "excluded unless certified as medically necessary."),
    ("7.1 PRE-EXISTING DISEASES",
     "Expenses related to the treatment of a pre-existing disease and its direct "
     "complications are excluded until the expiry of thirty-six months of continuous "
     "coverage from the first policy inception date."),
    ("7.2 COSMETIC AND AESTHETIC TREATMENT",
     "Expenses for cosmetic or plastic surgery are excluded unless required as part of "
     "medically necessary treatment to remove a direct consequence of an accident, burn "
     "or cancer, and certified by the attending medical practitioner."),
    ("7.5 DENTAL TREATMENT",
     "Dental treatment is excluded unless it requires hospitalisation and arises from an "
     "accidental injury sustained during the policy period."),
    ("8.1 CO-PAYMENT",
     "Each and every claim under this policy is subject to a co-payment of ten percent of "
     "the admissible claim amount, borne by the insured person. The co-payment applies "
     "after all other deductions."),
    ("8.3 SUB-LIMITS ON SPECIFIED PROCEDURES",
     "Cataract surgery is limited to 40,000 rupees per eye per policy year. Knee "
     "replacement is limited to 200,000 rupees per joint. Amounts in excess of these "
     "limits are not payable."),
    ("9.1 CLAIM NOTIFICATION",
     "The insurer must be notified within twenty-four hours of an emergency admission and "
     "at least forty-eight hours before a planned admission. Late notification may result "
     "in the claim being investigated before settlement."),
    ("9.3 DUPLICATE AND ERRONEOUS CHARGES",
     "Charges billed more than once for the same service on the same date of service are "
     "not payable. The insurer reserves the right to recover amounts paid in respect of "
     "duplicate charges."),
    ("10.2 FRAUDULENT CLAIMS",
     "If a claim is in any respect fraudulent, or if any fraudulent means are used by the "
     "insured person to obtain benefit, all benefits under this policy shall be forfeited "
     "and premiums paid shall not be refunded."),
]

SUM_INSURED = 500000.0
ROOM_RENT_CAP = 5000.0  # 1% of sum insured per day, per clause 4.1


def render_policy() -> bytes:
    """Lay the clauses out as a document the parser reads like any other."""
    lines = [
        "MERIDIAN HEALTH ASSURANCE",
        "SECURE FAMILY FLOATER - POLICY WORDING",
        "Policy Number: MHA-FF-2026-00417",
        f"Sum Insured: {SUM_INSURED:,.0f}",
        "",
    ]
    for header, body in POLICY_CLAUSES:
        lines.append(header)
        # Wrapped to a sensible measure so the layout-aware chunker sees real
        # lines rather than one enormous one.
        current = ""
        for word in body.split():
            if len(current) + len(word) + 1 > 92:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines.append(current)
        lines.append("")
    return text_layer_pdf(lines)


# ---------------------------------------------------------------------------
# The bills
# ---------------------------------------------------------------------------
# Each entry describes what a hospital printed. Verdicts, risk signals and
# citations are deliberately absent — they are produced by running the pipeline
# over the rendered document.

BILLS = [
    {
        "key": "clean",
        "reference": "CLM-SEED-CLEAN",
        "claimant": ("Ananya Rao", "MBR-4471"),
        "provider": ("Sunrise Multispeciality Hospital", "Bengaluru"),
        "admission": datetime.date(2026, 7, 12),
        "discharge": datetime.date(2026, 7, 15),
        "note": "A straightforward admission with nothing unusual.",
        "items": [
            ("Room Rent", "Shared room accommodation", 4500.0, 3),
            ("Surgeon Fees", "Laparoscopic appendectomy", 62000.0, 1),
            ("Diagnostics", "CBC CRP and abdominal ultrasound", 8200.0, 1),
            ("Pharmacy", "Post-operative antibiotics and analgesia", 6400.0, 1),
        ],
    },
    {
        "key": "capped",
        "reference": "CLM-SEED-CAPPED",
        "claimant": ("Rohit Mehta", "MBR-8823"),
        "provider": ("Lakeview Institute of Medical Sciences", "Pune"),
        "admission": datetime.date(2026, 7, 20),
        "discharge": datetime.date(2026, 7, 25),
        "note": "Room rate above the policy limit, plus excluded consumables.",
        "items": [
            ("Room Rent", "Single private room accommodation", 9000.0, 5),
            ("Surgeon Fees", "Open cholecystectomy", 78000.0, 1),
            ("Consumables", "Surgical gloves and disposable drapes", 3100.0, 1),
            ("Pharmacy", "IV antibiotics analgesia and antiemetics", 11800.0, 1),
            ("Diagnostics", "Liver function panel and HIDA scan", 14200.0, 1),
        ],
    },
    {
        "key": "flagged",
        "reference": "CLM-SEED-FLAGGED",
        "claimant": ("Priya Nair", "MBR-1094"),
        "provider": ("Grandview Care Centre", "Hyderabad"),
        "admission": datetime.date(2026, 7, 3),
        "discharge": datetime.date(2026, 7, 6),
        "note": "Contains a genuine duplicate line and excluded comfort items.",
        "items": [
            ("Room Rent", "Shared room accommodation", 4000.0, 3),
            ("Diagnostics", "MRI lumbar spine", 18500.0, 1),
            ("Diagnostics", "MRI lumbar spine", 18500.0, 1),
            ("Consumables", "Attendant meals and toiletries", 4300.0, 1),
            ("Pharmacy", "Analgesia and muscle relaxants", 9000.0, 1),
            ("Surgeon Fees", "Epidural steroid injection", 34000.0, 1),
        ],
    },
    {
        "key": "complex",
        "reference": "CLM-SEED-COMPLEX",
        "claimant": ("Devendra Iyer", "MBR-6620"),
        "provider": ("Northgate Hospital and Research Institute", "Chennai"),
        "admission": datetime.date(2026, 6, 18),
        "discharge": datetime.date(2026, 6, 29),
        "note": "Long stay, many lines, one service dated after discharge.",
        "items": [
            ("Room Rent", "Single room accommodation", 7500.0, 11),
            ("Surgeon Fees", "Coronary artery bypass graft", 285000.0, 1),
            ("Surgeon Fees", "Anaesthetist fees", 46000.0, 1),
            ("Diagnostics", "Coronary angiography", 42000.0, 1),
            ("Diagnostics", "Serial troponin and lipid panel", 11400.0, 1),
            ("Diagnostics", "Routine vitamin D screening", 2800.0, 1),
            ("Consumables", "Hand sanitiser and disposable bed sheets", 5600.0, 1),
            ("Pharmacy", "Anticoagulants statins and analgesia", 38700.0, 1),
            ("Other", "Ambulance transfer", 4500.0, 1),
        ],
        # Dated after discharge on purpose, so the date rule has something real
        # to find rather than being demonstrated on invented data.
        "late_line": ("Pharmacy", "Take-home medication 30 days", 9200.0,
                      datetime.date(2026, 7, 4)),
    },
]


def render_bill(spec: dict) -> bytes:
    """Render a bill as a hospital would print it."""
    lines = [
        spec["provider"][0].upper(),
        spec["provider"][1],
        "TAX INVOICE - INPATIENT SERVICES",
        "",
        f"Patient: {spec['claimant'][0]}",
        f"Member ID: {spec['claimant'][1]}",
        f"Admitted: {spec['admission'].isoformat()}",
        f"Discharged: {spec['discharge'].isoformat()}",
        "",
        "PARTICULARS                              QTY      RATE      AMOUNT",
        "",
    ]

    rows = [(c, d, r, q, spec["admission"]) for c, d, r, q in spec["items"]]
    if spec.get("late_line"):
        category, description, rate, when = spec["late_line"]
        rows.append((category, description, rate, 1, when))

    total = 0.0
    for category, description, rate, quantity, when in rows:
        amount = rate * quantity
        total += amount
        lines.append(f"{description[:40]:<40} {quantity:>3}  {rate:>8,.0f}  {amount:>10,.0f}")
        lines.append(f"   {category} - service date {when.isoformat()}")

    lines += ["", f"{'TOTAL PAYABLE':<40} {'':>3}  {'':>8}  {total:>10,.0f}", ""]
    return text_layer_pdf(lines)


class SeedContext(dict):
    """Stands in for the arq job context.

    The tasks publish progress to `ctx['redis']`; there is no queue here, so the
    key is absent and `publish_progress` quietly no-ops. The tasks themselves are
    the real ones.
    """

    def __init__(self):
        super().__init__(job_id="seed")


async def _store(payload: bytes, prefix: str, filename: str) -> str:
    key = f"{prefix}/{uuid.uuid4()}/{filename}"
    return await asyncio.to_thread(storage.put, key, payload)


async def _clear_previous(session) -> int:
    """Remove anything a previous seed created, so re-running replaces it."""
    refs = [b["reference"] for b in BILLS]
    claims = (
        await session.execute(select(Claim).where(Claim.reference.in_(refs)))
    ).scalars().all()
    for claim in claims:
        await session.delete(claim)

    await session.execute(delete(Document).where(Document.policy_id == sid("policy")))
    policy = await session.get(Policy, sid("policy"))
    if policy:
        await session.delete(policy)

    await session.flush()
    return len(claims)


async def seed() -> int:
    ctx = SeedContext()

    async with AsyncSessionLocal() as session:
        org, analyst = await ensure_demo_tenant(session)
        removed = await _clear_previous(session)
        await session.commit()
        org_id = org.id
        analyst_id = analyst.id if analyst else None

    if removed:
        print(f"Removed {removed} previously seeded claim(s).")

    # --- policy -------------------------------------------------------------
    print("Rendering and ingesting the policy document...")
    policy_pdf = render_policy()
    policy_key = await _store(policy_pdf, "policies", "meridian-secure-family-floater.pdf")

    async with AsyncSessionLocal() as session:
        policy = Policy(
            id=sid("policy"),
            organization_id=org_id,
            insurer_name="Meridian Health Assurance",
            policy_name="Meridian Secure Family Floater",
            policy_number="MHA-FF-2026-00417",
            effective_from=datetime.date(2026, 1, 1),
            effective_to=datetime.date(2026, 12, 31),
            sum_insured=SUM_INSURED,
            room_rent_cap=ROOM_RENT_CAP,
        )
        session.add(policy)
        await session.flush()

        policy_doc = Document(
            organization_id=org_id,
            policy_id=policy.id,
            kind=DocumentKind.POLICY,
            filename="meridian-secure-family-floater.pdf",
            byte_size=len(policy_pdf),
            storage_key=policy_key,
        )
        session.add(policy_doc)
        await session.commit()
        policy_id, policy_doc_id = str(policy.id), str(policy_doc.id)

    result = await ingest_policy_task(ctx, policy_id, policy_doc_id)
    if result.get("status") != "success":
        print(f"  ! policy ingestion failed: {result}", file=sys.stderr)
        return 1
    print(
        f"  parsed into {result['total_chunks']} passages "
        f"over {result['pages']} page(s)"
    )

    # --- claims -------------------------------------------------------------
    if not LLM_AVAILABLE:
        print(
            "\nNo GROQ_API_KEY configured. Documents will be parsed and stored, but the\n"
            "claims cannot be adjudicated and will be left visibly un-adjudicated.\n"
        )

    for spec in BILLS:
        print(f"\n{spec['reference']}  ({spec['note']})")
        bill_pdf = render_bill(spec)
        bill_key = await _store(bill_pdf, "bills", f"{spec['key']}-bill.pdf")

        async with AsyncSessionLocal() as session:
            # Get-or-create: claimants and providers outlive the claims that
            # reference them (the foreign key nulls rather than cascades), so a
            # re-seed must reuse them instead of colliding on the stable id.
            claimant = await session.get(Claimant, sid(f"claimant-{spec['key']}"))
            if claimant is None:
                claimant = Claimant(
                    id=sid(f"claimant-{spec['key']}"),
                    organization_id=org_id,
                    full_name=spec["claimant"][0],
                    member_id=spec["claimant"][1],
                )
                session.add(claimant)

            provider = await session.get(Provider, sid(f"provider-{spec['key']}"))
            if provider is None:
                provider = Provider(
                    id=sid(f"provider-{spec['key']}"),
                    organization_id=org_id,
                    name=spec["provider"][0],
                    city=spec["provider"][1],
                )
                session.add(provider)

            await session.flush()

            claim = Claim(
                organization_id=org_id,
                created_by_id=analyst_id,
                claimant_id=claimant.id,
                provider_id=provider.id,
                policy_id=uuid.UUID(policy_id),
                reference=spec["reference"],
                status=ClaimStatus.RECEIVED,
            )
            session.add(claim)
            await session.flush()

            document = Document(
                organization_id=org_id,
                claim_id=claim.id,
                kind=DocumentKind.BILL,
                filename=f"{spec['key']}-bill.pdf",
                byte_size=len(bill_pdf),
                storage_key=bill_key,
            )
            session.add(document)
            await session.commit()
            claim_id, document_id = str(claim.id), str(document.id)

        extracted = await extract_bill_task(ctx, claim_id, document_id)
        if extracted.get("status") != "success":
            print(f"  extraction did not complete: {extracted.get('error', extracted)}")
            continue
        print(
            f"  extracted {extracted['total_items']} line item(s); "
            f"{extracted['located']} located on the page"
        )

        audited = await audit_claim_task(ctx, claim_id, policy_id)
        if audited.get("status") == "success":
            risk = audited["risk"]
            print(
                f"  adjudicated {audited['total_items_audited']} item(s); "
                f"risk {risk['score']:.0f}/100 ({risk['band']}) "
                f"from {risk['signals']} signal(s)"
            )
        else:
            print(f"  not adjudicated: {audited.get('message') or audited.get('reason')}")

    print("\nSeed complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(seed()))
