"""Deterministic demo data.

Creates four claims spanning the risk range so a reviewer can open the app and
understand the product without uploading anything:

    CLM-SEED-CLEAN    every line covered, nothing to argue with
    CLM-SEED-CAPPED   room rent above the policy limit
    CLM-SEED-FLAGGED  duplicate billing and an excluded consumable
    CLM-SEED-COMPLEX  eleven lines, conflicting dates, mixed verdicts

Everything written here is attributed to a model version literally named
"seed/deterministic-fixture". Findings in these claims were not produced by a
model, and the UI must be able to tell a reviewer that rather than presenting
fixture text as live AI output.

Idempotent: re-running deletes the four seeded claims and rebuilds them.

    docker compose run --rm fastapi python scripts/seed.py
"""

import asyncio
import datetime
import pathlib
import sys
import uuid

# Running `python scripts/seed.py` puts scripts/ on sys.path, not the backend
# root, so the application packages would not import.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.bootstrap import ensure_demo_tenant
from core.database import AsyncSessionLocal
from models import (
    AdjudicationStatus,
    AuditFinding,
    Claim,
    ClaimItem,
    Claimant,
    ClaimStatus,
    Contradiction,
    Document,
    DocumentChunk,
    DocumentKind,
    DocumentStatus,
    Event,
    EventKind,
    ModelVersion,
    Policy,
    Provider,
    RiskBand,
    RiskScore,
    RiskSignal,
    SignalDirection,
)

# Stable ids so re-seeding replaces rather than duplicates, and so links into
# the app keep working across resets.
NS = uuid.UUID("6f1a9d2c-4b7e-4c31-9f80-2a6d5e0b7c14")


def sid(name: str) -> uuid.UUID:
    return uuid.uuid5(NS, name)


SEED_MODEL = "seed/deterministic-fixture"

TODAY = datetime.date(2026, 8, 1)


POLICY_CLAUSES = [
    ("4.1 ROOM RENT LIMIT", 4,
     "Room rent is payable up to 1% of the sum insured per day for a shared room "
     "and 2% for a single private room. Charges in excess of this limit are borne "
     "by the insured. Proportionate deduction applies to associated medical "
     "expenses where the room category exceeds the eligible limit."),
    ("4.2 NON-MEDICAL CONSUMABLES", 4,
     "Items of personal comfort and convenience, including but not limited to "
     "gloves, sanitiser, disposable bed sheets, attendant meals and toiletries, "
     "are excluded from coverage and are not payable under this policy."),
    ("5.1 SURGICAL PROCEDURES", 5,
     "Surgeon fees, anaesthetist fees and operation theatre charges for medically "
     "necessary surgical procedures are covered in full, subject to the sum insured "
     "and to pre-authorisation where the procedure is planned."),
    ("5.4 DIAGNOSTIC INVESTIGATIONS", 5,
     "Pathology and radiology investigations directly related to the admitted "
     "condition are covered. Routine screening not connected to the diagnosis is "
     "not payable."),
    ("6.2 PHARMACY", 6,
     "Drugs and consumables prescribed by the treating physician during the period "
     "of hospitalisation are covered when supported by a valid prescription."),
    ("9.3 DUPLICATE AND ERRONEOUS CHARGES", 9,
     "Charges billed more than once for the same service on the same date of "
     "service are not payable. The insurer reserves the right to recover amounts "
     "paid in respect of duplicate charges."),
    # --- Remaining clauses --------------------------------------------------
    # Appended, never inserted: the six above are referenced by index from the
    # CLAIMS specs below. A real policy runs to dozens of clauses, and a
    # six-clause corpus makes retrieval look trivially easy — top-5 of six is
    # not a measurement.
    ("1.1 DEFINITIONS", 1,
     "In this policy, 'Insured Person' means the individual named in the schedule. "
     "'Hospital' means an institution registered with the local authorities having "
     "at least ten inpatient beds, qualified nursing staff on duty at all times, "
     "and a fully equipped operation theatre."),
    ("1.4 WAITING PERIODS", 2,
     "Expenses related to the treatment of any illness diagnosed within thirty days "
     "of the first policy commencement date are not payable, other than claims "
     "arising from accidental injury."),
    ("2.1 PRE-HOSPITALISATION EXPENSES", 2,
     "Medical expenses incurred in the sixty days immediately before the date of "
     "admission are payable, provided they relate to the same condition for which "
     "hospitalisation was required and the inpatient claim has been admitted."),
    ("2.2 POST-HOSPITALISATION EXPENSES", 2,
     "Medical expenses incurred in the ninety days immediately following discharge "
     "are payable where they relate directly to the condition treated during the "
     "admission, subject to the sum insured."),
    ("3.1 DAY CARE PROCEDURES", 3,
     "Procedures listed in Annexure B which require less than twenty-four hours of "
     "hospitalisation due to technological advancement are covered. Outpatient "
     "treatment not requiring admission is not covered under this section."),
    ("3.4 AMBULANCE CHARGES", 3,
     "Road ambulance charges for transporting the insured person to hospital are "
     "reimbursed up to 2,000 rupees per hospitalisation, provided the admission is "
     "an admissible claim under this policy."),
    ("5.2 ANAESTHETIST AND SPECIALIST FEES", 5,
     "Fees charged by the anaesthetist, specialist consultants and the operating "
     "team in respect of a covered surgical procedure are payable at actuals, "
     "subject to reasonable and customary charges for the geography."),
    ("5.3 IMPLANTS AND PROSTHESES", 5,
     "The cost of implants, stents and prostheses used during a covered surgical "
     "procedure is payable where supported by the invoice and the batch record. "
     "Cosmetic implants are excluded."),
    ("5.5 SECOND OPINION", 5,
     "Charges for a second medical opinion obtained at the insured person's own "
     "initiative are not payable unless the insurer requested the opinion in writing."),
    ("6.1 CONSULTATION CHARGES", 6,
     "Charges for consultations by the treating physician during the period of "
     "hospitalisation are covered. Consultations unrelated to the admitted "
     "condition are not payable."),
    ("6.4 NURSING CHARGES", 6,
     "General nursing charges forming part of the room tariff are covered. Charges "
     "for a private duty nurse engaged at the request of the insured person or the "
     "family are excluded unless certified as medically necessary."),
    ("7.1 PRE-EXISTING DISEASES", 7,
     "Expenses related to the treatment of a pre-existing disease and its direct "
     "complications are excluded until the expiry of thirty-six months of continuous "
     "coverage from the first policy inception date."),
    ("7.2 COSMETIC AND AESTHETIC TREATMENT", 7,
     "Expenses for cosmetic or plastic surgery are excluded unless required as part "
     "of medically necessary treatment to remove a direct consequence of an accident, "
     "burn or cancer, and certified by the attending medical practitioner."),
    ("7.5 DENTAL TREATMENT", 7,
     "Dental treatment is excluded unless it requires hospitalisation and arises from "
     "an accidental injury sustained during the policy period."),
    ("8.1 CO-PAYMENT", 8,
     "Each and every claim under this policy is subject to a co-payment of ten percent "
     "of the admissible claim amount, borne by the insured person. The co-payment "
     "applies after all other deductions."),
    ("8.3 SUB-LIMITS ON SPECIFIED PROCEDURES", 8,
     "Cataract surgery is limited to 40,000 rupees per eye per policy year. Knee "
     "replacement is limited to 200,000 rupees per joint. Amounts in excess of these "
     "limits are not payable."),
    ("9.1 CLAIM NOTIFICATION", 9,
     "The insurer must be notified within twenty-four hours of an emergency admission "
     "and at least forty-eight hours before a planned admission. Late notification may "
     "result in the claim being investigated before settlement."),
    ("10.2 FRAUDULENT CLAIMS", 10,
     "If a claim is in any respect fraudulent, or if any fraudulent means are used by "
     "the insured person to obtain benefit, all benefits under this policy shall be "
     "forfeited and premiums paid shall not be refunded."),
]


# (category, description, billed, status, reason, clause_index, capped_amount)
CLAIMS = [
    {
        "key": "clean",
        "reference": "CLM-SEED-CLEAN",
        "claimant": ("Ananya Rao", "MBR-4471"),
        "provider": ("Sunrise Multispeciality Hospital", "Bengaluru"),
        "status": ClaimStatus.AUDIT_COMPLETE,
        "admission": datetime.date(2026, 7, 12),
        "discharge": datetime.date(2026, 7, 15),
        "risk": (12.0, RiskBand.LOW),
        "signals": [
            ("DOCUMENTATION_COMPLETE", "Discharge summary corroborates every billed line",
             SignalDirection.MITIGATING, -8.0,
             "All eleven billed services appear in the discharge summary with matching dates."),
            ("WITHIN_POLICY_LIMITS", "No line exceeds a policy limit",
             SignalDirection.MITIGATING, -6.0,
             "Room category and per-day rate are inside the 1% shared-room limit."),
        ],
        "items": [
            ("Room Rent", "Shared room, 3 days @ 4,500/day", 13500.0,
             AdjudicationStatus.APPROVED,
             "Shared room at 4,500/day is within the 1% of sum insured per-day limit.", 0, None),
            ("Surgeon Fees", "Laparoscopic appendectomy", 62000.0,
             AdjudicationStatus.APPROVED,
             "Medically necessary surgical procedure, covered in full under 5.1.", 2, None),
            ("Diagnostics", "CBC, CRP, abdominal ultrasound", 8200.0,
             AdjudicationStatus.APPROVED,
             "Investigations directly related to the admitted condition.", 3, None),
            ("Pharmacy", "Post-operative antibiotics and analgesia", 6400.0,
             AdjudicationStatus.APPROVED,
             "Prescribed during hospitalisation and supported by the prescription on file.", 4, None),
        ],
    },
    {
        "key": "capped",
        "reference": "CLM-SEED-CAPPED",
        "claimant": ("Rohit Mehta", "MBR-8823"),
        "provider": ("Lakeview Institute of Medical Sciences", "Pune"),
        "status": ClaimStatus.AUDIT_COMPLETE,
        "admission": datetime.date(2026, 7, 20),
        "discharge": datetime.date(2026, 7, 25),
        "risk": (44.0, RiskBand.MEDIUM),
        "signals": [
            ("ROOM_RENT_CAP_BREACH", "Room rent exceeds the eligible per-day limit",
             SignalDirection.AGGRAVATING, 18.0,
             "Billed 9,000/day against an eligible 5,000/day under clause 4.1."),
            ("PROPORTIONATE_DEDUCTION_RISK", "Associated expenses subject to proportionate deduction",
             SignalDirection.AGGRAVATING, 12.0,
             "Room category above entitlement triggers proportionate deduction on linked charges."),
            ("PRESCRIPTION_ON_FILE", "Pharmacy charges supported by prescription",
             SignalDirection.MITIGATING, -6.0,
             "Every pharmacy line maps to a prescribed drug in the discharge summary."),
        ],
        "items": [
            ("Room Rent", "Single private room, 5 days @ 9,000/day", 45000.0,
             AdjudicationStatus.CAPPED,
             "Eligible limit is 5,000 per day under clause 4.1. The excess of 4,000 per day "
             "across 5 days is not payable.", 0, 25000.0),
            ("Surgeon Fees", "Open cholecystectomy", 78000.0,
             AdjudicationStatus.APPROVED,
             "Medically necessary surgical procedure covered under 5.1.", 2, None),
            ("Consumables", "Surgical gloves and disposable drapes", 3100.0,
             AdjudicationStatus.REJECTED,
             "Non-medical consumables are explicitly excluded under clause 4.2.", 1, None),
            ("Pharmacy", "IV antibiotics, analgesia, antiemetics", 11800.0,
             AdjudicationStatus.APPROVED,
             "Prescribed during hospitalisation, covered under clause 6.2.", 4, None),
            ("Diagnostics", "Liver function panel, HIDA scan", 14200.0,
             AdjudicationStatus.APPROVED,
             "Investigations directly related to the admitted condition.", 3, None),
        ],
    },
    {
        "key": "flagged",
        "reference": "CLM-SEED-FLAGGED",
        "claimant": ("Priya Nair", "MBR-1094"),
        "provider": ("Grandview Care Centre", "Hyderabad"),
        "status": ClaimStatus.AUDIT_COMPLETE,
        "admission": datetime.date(2026, 7, 3),
        "discharge": datetime.date(2026, 7, 6),
        "risk": (81.0, RiskBand.HIGH),
        "signals": [
            ("DUPLICATE_LINE_ITEM", "Same procedure billed twice on one date of service",
             SignalDirection.AGGRAVATING, 26.0,
             "MRI lumbar spine appears twice on 04 Jul 2026 at an identical amount."),
            ("EXCLUDED_ITEM_BILLED", "Explicitly excluded consumables billed to the insurer",
             SignalDirection.AGGRAVATING, 19.0,
             "Attendant meals and toiletries are named exclusions under clause 4.2."),
            ("AMOUNT_DEVIATION", "Diagnostic charges well above peer range",
             SignalDirection.AGGRAVATING, 17.0,
             "MRI billed at 18,500 against a 6,000-9,000 range for comparable providers."),
            ("SHORT_STAY_HIGH_VALUE", "High billed value across a three-day admission",
             SignalDirection.AGGRAVATING, 11.0,
             "Total billed of 96,300 over three days is atypical for the recorded diagnosis."),
            ("PROVIDER_REGISTERED", "Provider is registered and in-network",
             SignalDirection.MITIGATING, -9.0,
             "Registration number verified against the network directory."),
        ],
        "items": [
            ("Room Rent", "Shared room, 3 days @ 4,000/day", 12000.0,
             AdjudicationStatus.APPROVED,
             "Within the shared-room per-day limit under clause 4.1.", 0, None),
            ("Diagnostics", "MRI lumbar spine (04 Jul)", 18500.0,
             AdjudicationStatus.NEEDS_REVIEW,
             "Charge is materially above the peer range for this investigation. The policy "
             "does not set a rate limit, so a human must decide whether to allow it.", 3, None),
            ("Diagnostics", "MRI lumbar spine (04 Jul)", 18500.0,
             AdjudicationStatus.REJECTED,
             "Duplicate of the preceding line: same service, same date of service. "
             "Not payable under clause 9.3.", 5, None),
            ("Consumables", "Attendant meals and toiletries", 4300.0,
             AdjudicationStatus.REJECTED,
             "Personal comfort items are excluded under clause 4.2.", 1, None),
            ("Pharmacy", "Analgesia and muscle relaxants", 9000.0,
             AdjudicationStatus.APPROVED,
             "Prescribed during hospitalisation, covered under clause 6.2.", 4, None),
            ("Surgeon Fees", "Epidural steroid injection", 34000.0,
             AdjudicationStatus.APPROVED,
             "Medically necessary procedure covered under clause 5.1.", 2, None),
        ],
        "contradiction": (
            "Discharge summary and bill disagree on the date of the MRI",
            "The discharge summary records a single MRI on 05 Jul 2026. The bill carries "
            "two MRI lines both dated 04 Jul 2026.",
            RiskBand.HIGH,
        ),
    },
    {
        "key": "complex",
        "reference": "CLM-SEED-COMPLEX",
        "claimant": ("Devendra Iyer", "MBR-6620"),
        "provider": ("Northgate Hospital and Research Institute", "Chennai"),
        "status": ClaimStatus.AUDIT_COMPLETE,
        "admission": datetime.date(2026, 6, 18),
        "discharge": datetime.date(2026, 6, 29),
        "risk": (63.0, RiskBand.HIGH),
        "signals": [
            ("ADMISSION_DATE_MISMATCH", "Admission date differs across documents",
             SignalDirection.AGGRAVATING, 21.0,
             "Bill states 18 Jun 2026; the discharge summary states 19 Jun 2026."),
            ("ROOM_RENT_CAP_BREACH", "Room rent exceeds the eligible per-day limit",
             SignalDirection.AGGRAVATING, 15.0,
             "Billed 7,500/day against an eligible 5,000/day under clause 4.1."),
            ("EXCLUDED_ITEM_BILLED", "Excluded consumables billed across two lines",
             SignalDirection.AGGRAVATING, 13.0,
             "Sanitiser and disposable bed sheets are named exclusions under clause 4.2."),
            ("LONG_STAY_DOCUMENTED", "Extended stay supported by daily progress notes",
             SignalDirection.MITIGATING, -12.0,
             "Eleven days of progress notes corroborate the length of stay."),
            ("PREAUTH_ON_FILE", "Planned procedure was pre-authorised",
             SignalDirection.MITIGATING, -8.0,
             "Pre-authorisation reference recorded against the surgical line."),
        ],
        "items": [
            ("Room Rent", "Single room, 11 days @ 7,500/day", 82500.0,
             AdjudicationStatus.CAPPED,
             "Eligible limit is 5,000 per day. Excess of 2,500 per day across 11 days "
             "is not payable under clause 4.1.", 0, 55000.0),
            ("Surgeon Fees", "Coronary artery bypass graft", 285000.0,
             AdjudicationStatus.APPROVED,
             "Pre-authorised medically necessary procedure, covered under clause 5.1.", 2, None),
            ("Surgeon Fees", "Anaesthetist fees", 46000.0,
             AdjudicationStatus.APPROVED,
             "Anaesthetist fees are covered alongside the surgical procedure under 5.1.", 2, None),
            ("Diagnostics", "Coronary angiography", 42000.0,
             AdjudicationStatus.APPROVED,
             "Directly related to the admitted cardiac condition.", 3, None),
            ("Diagnostics", "Serial troponin and lipid panel", 11400.0,
             AdjudicationStatus.APPROVED,
             "Investigations connected to the diagnosis under clause 5.4.", 3, None),
            ("Diagnostics", "Routine vitamin D screening", 2800.0,
             AdjudicationStatus.REJECTED,
             "Routine screening unconnected to the admitted condition is not payable "
             "under clause 5.4.", 3, None),
            ("Consumables", "Hand sanitiser and disposable bed sheets", 5600.0,
             AdjudicationStatus.REJECTED,
             "Personal comfort and convenience items are excluded under clause 4.2.", 1, None),
            ("Pharmacy", "Anticoagulants, statins, analgesia", 38700.0,
             AdjudicationStatus.APPROVED,
             "Prescribed during hospitalisation, covered under clause 6.2.", 4, None),
            ("Pharmacy", "Take-home medication, 30 days", 9200.0,
             AdjudicationStatus.NEEDS_REVIEW,
             "Clause 6.2 covers drugs supplied during hospitalisation. It is silent on "
             "post-discharge supply, so this requires a human decision.", 4, None),
            ("Room Rent", "ICU, 3 days @ 18,000/day", 54000.0,
             AdjudicationStatus.NEEDS_REVIEW,
             "The policy sets no explicit ICU sub-limit in the retrieved clauses. Whether "
             "the 1% room-rent limit applies to ICU must be confirmed.", 0, None),
            ("Other", "Ambulance transfer", 4500.0,
             AdjudicationStatus.NEEDS_REVIEW,
             "No retrieved clause addresses ambulance charges.", None, None),
        ],
        "contradiction": (
            "Admission date differs between the bill and the discharge summary",
            "The hospital bill records admission on 18 Jun 2026. The discharge summary "
            "records 19 Jun 2026. One day of room rent depends on which is correct.",
            RiskBand.MEDIUM,
        ),
    },
]


async def _clear_previous(session: AsyncSession) -> int:
    """Delete previously seeded claims so re-running does not duplicate them."""
    refs = [c["reference"] for c in CLAIMS]
    existing = (
        await session.execute(select(Claim).where(Claim.reference.in_(refs)))
    ).scalars().all()
    for claim in existing:
        await session.delete(claim)
    await session.flush()
    return len(existing)


def _embed(texts: list[str]) -> list[list[float]] | None:
    """Embed the seeded policy clauses so they are actually retrievable.

    Returns None if the embedding model is unavailable. The chunks are still
    written — the citations in seeded findings resolve either way — but semantic
    search will not surface them until they are embedded.
    """
    try:
        from agents.policy_ingestor import generate_embeddings

        return generate_embeddings(texts)
    except Exception as e:
        print(f"  ! could not embed seed clauses ({e}); writing them unembedded")
        return None


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        org, analyst = await ensure_demo_tenant(session)

        removed = await _clear_previous(session)
        if removed:
            print(f"Removed {removed} previously seeded claim(s).")

        model = (
            await session.execute(
                select(ModelVersion).where(ModelVersion.identifier == SEED_MODEL)
            )
        ).scalars().first()
        if model is None:
            model = ModelVersion(
                id=sid("model"),
                kind="llm",
                identifier=SEED_MODEL,
                provider="seed",
                notes=(
                    "Fixture data. Findings attributed to this version were written by "
                    "scripts/seed.py and were not produced by any model."
                ),
            )
            session.add(model)
            await session.flush()

        policy = await session.get(Policy, sid("policy"))
        if policy is None:
            policy = Policy(
                id=sid("policy"),
                organization_id=org.id,
                insurer_name="Meridian Health Assurance",
                policy_name="Meridian Secure Family Floater",
                policy_number="MHA-FF-2026-00417",
                effective_from=datetime.date(2026, 1, 1),
                effective_to=datetime.date(2026, 12, 31),
                sum_insured=500000.0,
                room_rent_cap=5000.0,
            )
            session.add(policy)
            await session.flush()

        policy_doc = await session.get(Document, sid("policy-doc"))
        if policy_doc is None:
            policy_doc = Document(
                id=sid("policy-doc"),
                organization_id=org.id,
                policy_id=policy.id,
                kind=DocumentKind.POLICY,
                status=DocumentStatus.PARSED,
                filename="meridian-secure-family-floater-2026.pdf",
                storage_key="seed://meridian-secure-family-floater-2026.pdf",
                page_count=12,
            )
            session.add(policy_doc)
            await session.flush()

        chunks = (
            await session.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == policy_doc.id)
            )
        ).scalars().all()

        # Reconcile rather than skip: POLICY_CLAUSES is authoritative, so a
        # stale set from an earlier definition is rebuilt instead of silently
        # leaving the corpus out of step with this file.
        if len(chunks) != len(POLICY_CLAUSES):
            for stale in chunks:
                await session.delete(stale)
            await session.flush()
            chunks = []

        if not chunks:
            vectors = _embed([text for _, _, text in POLICY_CLAUSES])
            chunks = []
            for ordinal, (header, page, text) in enumerate(POLICY_CLAUSES):
                chunk = DocumentChunk(
                    id=sid(f"chunk-{ordinal}"),
                    document_id=policy_doc.id,
                    policy_id=policy.id,
                    ordinal=ordinal,
                    page_number=page,
                    section_header=header,
                    text_content=text,
                    embedding=vectors[ordinal] if vectors else None,
                )
                session.add(chunk)
                chunks.append(chunk)
            await session.flush()
            print(f"Wrote {len(chunks)} policy clauses ({'embedded' if vectors else 'unembedded'}).")

        chunks = sorted(chunks, key=lambda c: c.ordinal)

        for spec in CLAIMS:
            key = spec["key"]

            claimant = await session.get(Claimant, sid(f"claimant-{key}"))
            if claimant is None:
                name, member_id = spec["claimant"]
                claimant = Claimant(
                    id=sid(f"claimant-{key}"),
                    organization_id=org.id,
                    full_name=name,
                    member_id=member_id,
                )
                session.add(claimant)

            provider = await session.get(Provider, sid(f"provider-{key}"))
            if provider is None:
                name, city = spec["provider"]
                provider = Provider(
                    id=sid(f"provider-{key}"),
                    organization_id=org.id,
                    name=name,
                    city=city,
                    registration_number=f"REG-{abs(hash(key)) % 90000 + 10000}",
                )
                session.add(provider)

            await session.flush()

            total_billed = sum(item[2] for item in spec["items"])
            total_approved = sum(
                (item[6] if item[6] is not None else item[2])
                for item in spec["items"]
                if item[3] in (AdjudicationStatus.APPROVED, AdjudicationStatus.CAPPED)
            )

            claim = Claim(
                id=sid(f"claim-{key}"),
                organization_id=org.id,
                created_by_id=analyst.id if analyst else None,
                claimant_id=claimant.id,
                provider_id=provider.id,
                policy_id=policy.id,
                reference=spec["reference"],
                status=spec["status"],
                total_billed=total_billed,
                total_approved=total_approved,
                admission_date=spec["admission"],
                discharge_date=spec["discharge"],
            )
            session.add(claim)
            await session.flush()

            for line_number, (category, description, billed, status, reason, clause_ix, capped) in enumerate(
                spec["items"], start=1
            ):
                item = ClaimItem(
                    claim_id=claim.id,
                    line_number=line_number,
                    category=category,
                    description=description,
                    billed_amount=billed,
                    allowed_amount=capped if capped is not None else (
                        billed if status in (AdjudicationStatus.APPROVED,) else None
                    ),
                )
                session.add(item)
                await session.flush()

                cited = chunks[clause_ix] if clause_ix is not None else None
                session.add(
                    AuditFinding(
                        claim_item_id=item.id,
                        model_version_id=model.id,
                        chunk_id=cited.id if cited else None,
                        status=status,
                        reason=reason,
                        policy_clause_cited=cited.section_header if cited else None,
                        original_clause_text=cited.text_content if cited else None,
                        page_number=cited.page_number if cited else None,
                        capped_amount=capped,
                        confidence=0.9 if cited else 0.35,
                    )
                )

            score, band = spec["risk"]
            signals = spec["signals"]
            for code, title, direction, weight, detail in signals:
                session.add(
                    RiskSignal(
                        claim_id=claim.id,
                        code=code,
                        title=title,
                        detail=detail,
                        direction=direction,
                        weight=weight,
                    )
                )

            session.add(
                RiskScore(
                    claim_id=claim.id,
                    model_version_id=model.id,
                    score=score,
                    band=band,
                    signal_count=len(signals),
                    breakdown=[
                        {"code": code, "title": title, "weight": weight}
                        for code, title, _direction, weight, _detail in signals
                    ],
                )
            )

            if spec.get("contradiction"):
                summary, detail, severity = spec["contradiction"]
                session.add(
                    Contradiction(
                        claim_id=claim.id,
                        summary=summary,
                        detail=detail,
                        severity=severity,
                    )
                )

            base = datetime.datetime.combine(
                spec["discharge"], datetime.time(9, 0), tzinfo=datetime.timezone.utc
            )
            timeline = [
                (EventKind.SYSTEM, "Claim received", None),
                (EventKind.EVIDENCE, "Hospital bill and policy document attached", None),
                (EventKind.AI_FINDING, f"{len(spec['items'])} line items adjudicated",
                 "Fixture data written by scripts/seed.py."),
                (EventKind.AI_FINDING, f"Risk scored {score:.0f}/100 ({band.value})",
                 f"{len(signals)} signals contributed."),
                (EventKind.STATUS_CHANGE, f"Status set to {spec['status'].value}", None),
            ]
            for offset, (kind, summary, detail) in enumerate(timeline):
                session.add(
                    Event(
                        claim_id=claim.id,
                        actor_id=analyst.id if analyst and kind == EventKind.HUMAN_ACTION else None,
                        kind=kind,
                        summary=summary,
                        detail=detail,
                        occurred_at=base + datetime.timedelta(minutes=offset * 7),
                    )
                )

            print(f"  {spec['reference']:<18} {len(spec['items']):>2} items  risk {score:>5.1f} ({band.value})")

        await session.commit()

    print("\nSeed complete. Four demo claims are available.")


if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as e:
        print(f"Seed failed: {e}", file=sys.stderr)
        raise
