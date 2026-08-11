"""Generate the demo bill and policy PDFs used by the "Use Demo Documents" button.

Run from the repo root:  python scripts/generate_demo_docs.py

The documents are deliberately designed so that the audit produces a mix of
APPROVED and REJECTED findings: without at least one rejection the appeal
generator short-circuits to NO_APPEAL_NEEDED and the demo ends early.
"""

import os

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "public")

_styles = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=_styles["BodyText"], fontSize=10, leading=14, spaceAfter=6)
H1 = ParagraphStyle("h1", parent=_styles["Heading1"], fontSize=16, spaceAfter=12)
H2 = ParagraphStyle("h2", parent=_styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=6)


def _build(filename, flowables):
    path = os.path.join(OUT_DIR, filename)
    doc = SimpleDocTemplate(
        path, pagesize=LETTER,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        topMargin=0.9 * inch, bottomMargin=0.9 * inch,
    )
    doc.build(flowables)
    print(f"wrote {path}")


# --------------------------------------------------------------------------
# Hospital bill
# --------------------------------------------------------------------------

BILL_LINES = [
    ("ER-99284", "Emergency Department Visit, Level 4", "1", "1,850.00"),
    ("RAD-71046", "X-Ray, Chest, 2 Views", "1", "420.00"),
    ("LAB-80053", "Comprehensive Metabolic Panel", "1", "310.00"),
    ("ROOM-PVT", "Private Room Accommodation Upgrade, 2 Nights", "2", "1,600.00"),
    ("CONS-NEU", "Neurology Consultation, Out-of-Network (no pre-authorization on file)", "1", "875.00"),
    ("MISC-CNV", "Patient Convenience Kit, In-Room Television and Telephone Service", "1", "145.00"),
]


def build_bill():
    flow = [
        Paragraph("ST. MARTIN REGIONAL MEDICAL CENTER", H1),
        Paragraph("1420 Harborview Avenue, Springfield, IL 62704<br/>Tax ID 36-4417290 &nbsp;|&nbsp; NPI 1962554417", BODY),
        Spacer(1, 10),
        Paragraph("STATEMENT OF CHARGES", H2),
        Paragraph(
            "Patient: Jordan A. Whitfield<br/>"
            "Account Number: 88-4471902<br/>"
            "Date of Service: March 14, 2026<br/>"
            "Insurance: Aetna Choice POS II &nbsp;|&nbsp; Member ID W884120336<br/>"
            "Statement Date: March 28, 2026",
            BODY,
        ),
        Spacer(1, 10),
        Paragraph("ITEMIZED CHARGES", H2),
    ]

    for code, desc, qty, amount in BILL_LINES:
        flow.append(Paragraph(
            f"<b>{code}</b> &nbsp; {desc} &nbsp;&nbsp; Qty: {qty} &nbsp;&nbsp; Charge: <b>${amount}</b>",
            BODY,
        ))

    flow += [
        Spacer(1, 12),
        Paragraph("<b>TOTAL CHARGES: $5,200.00</b>", BODY),
        Paragraph("Payments and Adjustments: $0.00", BODY),
        Paragraph("<b>BALANCE DUE: $5,200.00</b>", BODY),
        Spacer(1, 12),
        Paragraph(
            "This statement reflects charges submitted to your insurance carrier. "
            "Any amount determined to be non-covered under your plan becomes patient responsibility. "
            "Questions regarding coverage determinations should be directed to your carrier.",
            BODY,
        ),
    ]
    _build("demo-hospital-bill-2026.pdf", flow)


# --------------------------------------------------------------------------
# Insurance policy
# --------------------------------------------------------------------------

# Headings use the "<number>. TITLE" form because that is what
# agents/policy_ingestor._split_into_sections detects as a section header. Without a
# match the whole page collapses into one chunk and citations lose their granularity.
POLICY_SECTIONS = [
    ("1. SCHEDULE OF BENEFITS", [
        "Plan Year: January 1, 2026 through December 31, 2026.",
        "Individual Deductible: $250 per plan year for emergency services. Individual Out-of-Pocket Maximum: $6,500.",
        "This Certificate of Coverage describes the benefits available to Members enrolled in the Aetna Choice POS II plan. "
        "Benefits are subject to the exclusions and limitations set forth in Section 6.",
    ]),
    ("3. EMERGENCY AND URGENT CARE", [
        "<b>3.1 Emergency Department Services.</b> Medically necessary emergency department services are covered up to "
        "$5,000 per visit following satisfaction of the $250 emergency services deductible. Facility and professional "
        "charges billed under evaluation and management codes 99281 through 99285 are eligible for coverage under this provision.",
        "<b>3.2 Prudent Layperson Standard.</b> Coverage for emergency services is determined using the prudent layperson "
        "standard and is not contingent on the final diagnosis.",
    ]),
    ("4. DIAGNOSTIC AND LABORATORY SERVICES", [
        "<b>4.2 Diagnostic Imaging.</b> Medically necessary diagnostic radiology, including plain-film X-ray examinations, "
        "is covered at ninety percent (90%) of the allowed amount when performed by an in-network provider. The Member is "
        "responsible for the remaining ten percent (10%) as coinsurance.",
        "<b>4.5 Laboratory Services.</b> Standard laboratory panels, including comprehensive metabolic panels and complete "
        "blood counts, are covered at one hundred percent (100%) of the allowed amount when performed by an in-network "
        "laboratory and ordered by a treating provider.",
    ]),
    ("5. REFERRALS AND PRE-AUTHORIZATION", [
        "<b>5.2 Out-of-Network Specialist Consultations.</b> Consultations rendered by out-of-network specialist providers "
        "require pre-authorization obtained prior to the date of service. Services rendered by an out-of-network specialist "
        "<b>without pre-authorization on file are not covered</b>, and the full billed amount is the responsibility of the Member.",
        "<b>5.3 Retroactive Authorization.</b> Retroactive authorization may be granted only where the Member was medically "
        "incapacitated and unable to request authorization, and where the request is submitted within 48 hours of the service.",
    ]),
    ("6. EXCLUSIONS AND LIMITATIONS", [
        "The following are excluded from coverage under this plan:",
        "<b>6.3 Private Room Accommodation.</b> Charges for private room accommodation are <b>not covered</b> except where "
        "a private room is medically necessary for isolation purposes and has been pre-authorized by the Plan. Where a private "
        "room is not medically necessary, the differential between the semi-private room rate and the private room rate is the "
        "sole responsibility of the Member.",
        "<b>6.4 Cosmetic Procedures.</b> Procedures performed primarily to improve appearance are not covered.",
        "<b>6.7 Personal Comfort and Convenience Items.</b> Charges for personal comfort, convenience, or administrative items "
        "are <b>not covered</b>. Excluded items include, without limitation: in-room television and telephone service, guest meals "
        "and guest accommodations, personal hygiene and convenience kits, and record duplication fees.",
        "<b>6.9 Experimental or Investigational Services.</b> Services not recognized as standard of care are not covered.",
    ]),
    ("8. APPEALS", [
        "<b>8.1 Right to Appeal.</b> A Member may submit a written appeal of any adverse benefit determination within 180 days "
        "of receipt of the determination. The Plan will issue a written response within 30 days of receipt of a complete appeal.",
        "<b>8.2 External Review.</b> Following exhaustion of the internal appeal process, the Member may request an independent "
        "external review.",
    ]),
]


def build_policy():
    flow = [
        Paragraph("AETNA CHOICE POS II", H1),
        Paragraph("CERTIFICATE OF COVERAGE", H2),
        Paragraph("Group Policy Number GP-2026-44817 &nbsp;|&nbsp; Effective January 1, 2026", BODY),
        Spacer(1, 14),
    ]

    for index, (heading, paragraphs) in enumerate(POLICY_SECTIONS):
        flow.append(Paragraph(heading, H2))
        for text in paragraphs:
            flow.append(Paragraph(text, BODY))
        # Spread the document over several pages so cited page numbers are meaningful.
        if index in (1, 3):
            flow.append(PageBreak())

    _build("demo-aetna-policy-document.pdf", flow)


if __name__ == "__main__":
    build_bill()
    build_policy()
