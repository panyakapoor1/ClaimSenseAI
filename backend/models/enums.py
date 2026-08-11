"""Controlled vocabularies for the claim domain.

These are backed by native PostgreSQL enum types rather than free-form strings.
The prototype stored every status as an unconstrained `String`, which is how the
codebase ended up writing both "AUDIT_COMPLETE" and "COMPLETED" for the same
state and rendering an amber "unknown" badge for one of them.

Adding a value later is an explicit `ALTER TYPE ... ADD VALUE` in a migration.
That friction is deliberate: a new claim state should be a reviewed decision.
"""

import enum


class UserRole(str, enum.Enum):
    """Who a person is allowed to be. Enforcement lands in P3."""

    ANALYST = "ANALYST"
    SENIOR_ANALYST = "SENIOR_ANALYST"
    ADMIN = "ADMIN"
    AUDITOR = "AUDITOR"


class ClaimStatus(str, enum.Enum):
    """Lifecycle of a claim through the pipeline.

    Ordered by progression. Terminal failure states are grouped at the end so a
    reviewer can tell "still working" from "stopped" at a glance.
    """

    RECEIVED = "RECEIVED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    AUDITING = "AUDITING"
    AUDIT_COMPLETE = "AUDIT_COMPLETE"
    APPEAL_GENERATED = "APPEAL_GENERATED"
    NO_APPEAL_NEEDED = "NO_APPEAL_NEEDED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"


class AdjudicationStatus(str, enum.Enum):
    """Outcome for a single billed line item.

    CAPPED exists because the prototype's auditor prompt explicitly collapsed
    "covered but limited" into APPROVED, which loses the most common real finding
    in Indian health claims: a room-rent cap that partially disallows the charge.
    """

    APPROVED = "APPROVED"
    CAPPED = "CAPPED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class DocumentKind(str, enum.Enum):
    BILL = "BILL"
    POLICY = "POLICY"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    PRESCRIPTION = "PRESCRIPTION"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    OTHER = "OTHER"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    FAILED = "FAILED"


class RiskBand(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SignalDirection(str, enum.Enum):
    """Whether a fired signal raises or lowers risk.

    Corroborating evidence has to be able to subtract, otherwise a risk score is
    just a count of things that look bad and can never be argued down.
    """

    AGGRAVATING = "AGGRAVATING"
    MITIGATING = "MITIGATING"


class DecisionAction(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    OVERRIDE = "OVERRIDE"
    MARK_FALSE_POSITIVE = "MARK_FALSE_POSITIVE"
    CONFIRM_FRAUD = "CONFIRM_FRAUD"


class InvestigationStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class EventKind(str, enum.Enum):
    """Categories in the unified claim timeline.

    One ordered stream rather than several per-source lists, so "what happened
    and when" is a query instead of a UI-side merge.
    """

    SYSTEM = "SYSTEM"
    EVIDENCE = "EVIDENCE"
    AI_FINDING = "AI_FINDING"
    HUMAN_ACTION = "HUMAN_ACTION"
    STATUS_CHANGE = "STATUS_CHANGE"


class FactKind(str, enum.Enum):
    AMOUNT = "AMOUNT"
    DATE = "DATE"
    PERSON = "PERSON"
    PROVIDER = "PROVIDER"
    POLICY_NUMBER = "POLICY_NUMBER"
    PROCEDURE = "PROCEDURE"
    DIAGNOSIS = "DIAGNOSIS"
    OTHER = "OTHER"
