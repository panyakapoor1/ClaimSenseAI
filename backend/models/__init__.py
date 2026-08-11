"""Domain model.

Every model is imported here so that `Base.metadata` is fully populated by the
time Alembic reads it. A model that is only imported by the module that uses it
is invisible to autogenerate and silently missing from migrations.
"""

from .base import Base
from .enums import (
    AdjudicationStatus,
    ClaimStatus,
    DecisionAction,
    DocumentKind,
    DocumentStatus,
    EventKind,
    FactKind,
    InvestigationStatus,
    RiskBand,
    SignalDirection,
    UserRole,
)
from .org import Organization, User
from .policy import Policy
from .claim import AppealDocument, Claim, Claimant, ClaimItem, AuditFinding, Provider
from .document import EMBEDDING_DIM, Document, DocumentChunk, DocumentPage, ExtractedFact
from .intelligence import AIDecision, Contradiction, ModelVersion, RiskScore, RiskSignal
from .review import AuditLog, Event, HumanDecision, Investigation, InvestigationNote

__all__ = [
    "Base",
    # enums
    "AdjudicationStatus",
    "ClaimStatus",
    "DecisionAction",
    "DocumentKind",
    "DocumentStatus",
    "EventKind",
    "FactKind",
    "InvestigationStatus",
    "RiskBand",
    "SignalDirection",
    "UserRole",
    # identity
    "Organization",
    "User",
    # case
    "Claim",
    "Claimant",
    "ClaimItem",
    "AuditFinding",
    "AppealDocument",
    "Provider",
    "Policy",
    # evidence
    "Document",
    "DocumentPage",
    "DocumentChunk",
    "ExtractedFact",
    "EMBEDDING_DIM",
    # intelligence
    "AIDecision",
    "Contradiction",
    "ModelVersion",
    "RiskScore",
    "RiskSignal",
    # human loop
    "AuditLog",
    "Event",
    "HumanDecision",
    "Investigation",
    "InvestigationNote",
]
