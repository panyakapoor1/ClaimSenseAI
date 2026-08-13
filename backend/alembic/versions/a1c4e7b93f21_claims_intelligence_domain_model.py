"""Claims intelligence domain model

Replaces the prototype's seven-table schema with the full case / evidence /
intelligence / human-loop model.

DATA LOSS IS INTENTIONAL AND UNAVOIDABLE HERE. The legacy tables are dropped
rather than migrated in place, because the old rows cannot be carried across
faithfully: claims have no organization, claimant or reference; policy_chunks
have no owning document; and audit_findings stored page numbers as free text.
Inventing values for those columns would put fabricated data in the very tables
this rebuild exists to make trustworthy. The affected data is prototype test
data only.

`downgrade()` restores the legacy *structure* so the revision chain stays
reversible. It does not restore legacy data, which is gone.

Revision ID: a1c4e7b93f21
Revises: ff149997eb72
Create Date: 2026-08-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "a1c4e7b93f21"
down_revision: Union[str, None] = "ff149997eb72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMBEDDING_DIM = 384

# Native enum types, created once up front. Columns then reference them with
# create_type=False so no table definition tries to create them a second time.
ENUMS = {
    "user_role": ("ANALYST", "SENIOR_ANALYST", "ADMIN", "AUDITOR"),
    "claim_status": (
        "RECEIVED", "EXTRACTING", "EXTRACTED", "AUDITING", "AUDIT_COMPLETE",
        "APPEAL_GENERATED", "NO_APPEAL_NEEDED", "CLOSED", "FAILED", "LLM_UNAVAILABLE",
    ),
    "adjudication_status": ("APPROVED", "CAPPED", "REJECTED", "NEEDS_REVIEW"),
    "document_kind": (
        "BILL", "POLICY", "DISCHARGE_SUMMARY", "PRESCRIPTION", "DIAGNOSTIC_REPORT", "OTHER",
    ),
    "document_status": ("UPLOADED", "PARSING", "PARSED", "FAILED"),
    "risk_band": ("LOW", "MEDIUM", "HIGH", "CRITICAL"),
    "signal_direction": ("AGGRAVATING", "MITIGATING"),
    "decision_action": (
        "APPROVE", "REJECT", "ESCALATE", "REQUEST_EVIDENCE", "OVERRIDE",
        "MARK_FALSE_POSITIVE", "CONFIRM_FRAUD",
    ),
    "investigation_status": ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"),
    "event_kind": ("SYSTEM", "EVIDENCE", "AI_FINDING", "HUMAN_ACTION", "STATUS_CHANGE"),
    "fact_kind": (
        "AMOUNT", "DATE", "PERSON", "PROVIDER", "POLICY_NUMBER", "PROCEDURE",
        "DIAGNOSIS", "OTHER",
    ),
}

# Legacy tables, dropped children-first so foreign keys never block the drop.
LEGACY_TABLES = [
    "appeal_documents", "audit_findings", "claim_items", "policy_chunks",
    "claims", "policies", "users",
]

# Foreign keys are not indexed automatically by PostgreSQL, and every one of
# these is joined on or cascaded through.
FK_INDEXES = [
    ("users", "organization_id"),
    ("claimants", "organization_id"),
    ("providers", "organization_id"),
    ("policies", "organization_id"),
    ("claims", "organization_id"), ("claims", "created_by_id"), ("claims", "claimant_id"),
    ("claims", "provider_id"), ("claims", "policy_id"),
    ("claim_items", "claim_id"),
    ("documents", "organization_id"), ("documents", "claim_id"), ("documents", "policy_id"),
    ("document_pages", "document_id"),
    ("document_chunks", "document_id"), ("document_chunks", "policy_id"),
    ("audit_findings", "claim_item_id"), ("audit_findings", "model_version_id"),
    ("audit_findings", "chunk_id"),
    ("appeal_documents", "claim_id"), ("appeal_documents", "model_version_id"),
    ("extracted_facts", "claim_id"), ("extracted_facts", "document_id"),
    ("extracted_facts", "chunk_id"),
    ("ai_decisions", "claim_id"), ("ai_decisions", "model_version_id"),
    ("risk_signals", "claim_id"), ("risk_signals", "claim_item_id"),
    ("risk_scores", "claim_id"), ("risk_scores", "model_version_id"),
    ("contradictions", "claim_id"), ("contradictions", "left_fact_id"),
    ("contradictions", "right_fact_id"),
    ("investigations", "claim_id"), ("investigations", "opened_by_id"),
    ("investigations", "assigned_to_id"),
    ("investigation_notes", "investigation_id"), ("investigation_notes", "author_id"),
    ("human_decisions", "claim_id"), ("human_decisions", "claim_item_id"),
    ("human_decisions", "decided_by_id"), ("human_decisions", "ai_decision_id"),
    ("events", "claim_id"), ("events", "actor_id"),
    ("audit_logs", "actor_id"), ("audit_logs", "organization_id"),
]

# Blocks rewriting history at the database level, so the guarantee does not
# depend on every future caller remembering it.
#
# Kept as two separate statements: the asyncpg driver prepares each execute and
# rejects more than one command per statement.
AUDIT_LOG_GUARD_FN = """
CREATE OR REPLACE FUNCTION claimsense_audit_logs_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only; % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql
"""

AUDIT_LOG_GUARD_TRIGGER = """
CREATE TRIGGER audit_logs_append_only
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION claimsense_audit_logs_append_only()
"""


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def _fk(name: str, target: str, *, nullable: bool = False, ondelete: str = "CASCADE") -> sa.Column:
    return sa.Column(
        name, postgresql.UUID(as_uuid=True),
        sa.ForeignKey(target, ondelete=ondelete), nullable=nullable,
    )


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    for table in LEGACY_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    # --- identity -----------------------------------------------------------
    op.create_table(
        "organizations",
        _uuid_pk(),
        sa.Column("name", sa.String(200), nullable=False),
        # Uniqueness is enforced by the unique index below, not by a separate
        # UNIQUE constraint. `unique=True, index=True` on the model produces a
        # unique index only, and declaring both here would drift from it.
        sa.Column("slug", sa.String(80), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "users",
        _uuid_pk(),
        _fk("organization_id", "organizations.id"),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("role", _enum("user_role"), nullable=False, server_default="ANALYST"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        *_timestamps(),
    )

    # --- case ---------------------------------------------------------------
    op.create_table(
        "claimants",
        _uuid_pk(),
        _fk("organization_id", "organizations.id"),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("member_id", sa.String(120), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "providers",
        _uuid_pk(),
        _fk("organization_id", "organizations.id"),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("registration_number", sa.String(120), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "policies",
        _uuid_pk(),
        _fk("organization_id", "organizations.id"),
        sa.Column("insurer_name", sa.String(300), nullable=False),
        sa.Column("policy_name", sa.String(300), nullable=False),
        sa.Column("policy_number", sa.String(120), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("sum_insured", sa.Float(), nullable=True),
        sa.Column("room_rent_cap", sa.Float(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "model_versions",
        _uuid_pk(),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("identifier", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(80), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("kind", "identifier", name="uq_model_versions_kind_identifier"),
    )

    op.create_table(
        "claims",
        _uuid_pk(),
        _fk("organization_id", "organizations.id"),
        _fk("created_by_id", "users.id", nullable=True, ondelete="SET NULL"),
        _fk("claimant_id", "claimants.id", nullable=True, ondelete="SET NULL"),
        _fk("provider_id", "providers.id", nullable=True, ondelete="SET NULL"),
        _fk("policy_id", "policies.id", nullable=True, ondelete="SET NULL"),
        sa.Column("reference", sa.String(32), nullable=False),
        sa.Column("status", _enum("claim_status"), nullable=False, server_default="RECEIVED"),
        sa.Column("total_billed", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_approved", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("admission_date", sa.Date(), nullable=True),
        sa.Column("discharge_date", sa.Date(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_claims_status", "claims", ["status"])

    op.create_table(
        "claim_items",
        _uuid_pk(),
        _fk("claim_id", "claims.id"),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("procedure_code", sa.String(40), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("unit_price", sa.Float(), nullable=True),
        sa.Column("billed_amount", sa.Float(), nullable=False),
        sa.Column("allowed_amount", sa.Float(), nullable=True),
        sa.Column("service_date", sa.Date(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_claim_items_procedure_code", "claim_items", ["procedure_code"])

    # --- evidence -----------------------------------------------------------
    op.create_table(
        "documents",
        _uuid_pk(),
        _fk("organization_id", "organizations.id"),
        _fk("claim_id", "claims.id", nullable=True),
        _fk("policy_id", "policies.id", nullable=True),
        sa.Column("kind", _enum("document_kind"), nullable=False),
        sa.Column("status", _enum("document_status"), nullable=False, server_default="UPLOADED"),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False, server_default="application/pdf"),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_documents_checksum_sha256", "documents", ["checksum_sha256"])

    op.create_table(
        "document_pages",
        _uuid_pk(),
        _fk("document_id", "documents.id"),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False, server_default=""),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("from_ocr", sa.Boolean(), nullable=False, server_default="false"),
        *_timestamps(),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_page"),
    )

    op.create_table(
        "document_chunks",
        _uuid_pk(),
        _fk("document_id", "documents.id"),
        _fk("policy_id", "policies.id", nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_header", sa.String(500), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("bbox_x0", sa.Float(), nullable=True),
        sa.Column("bbox_y0", sa.Float(), nullable=True),
        sa.Column("bbox_x1", sa.Float(), nullable=True),
        sa.Column("bbox_y1", sa.Float(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_document_chunks_page_number", "document_chunks", ["page_number"])

    op.create_table(
        "audit_findings",
        _uuid_pk(),
        _fk("claim_item_id", "claim_items.id"),
        _fk("model_version_id", "model_versions.id", nullable=True, ondelete="SET NULL"),
        _fk("chunk_id", "document_chunks.id", nullable=True, ondelete="SET NULL"),
        sa.Column("status", _enum("adjudication_status"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("policy_clause_cited", sa.String(500), nullable=True),
        sa.Column("original_clause_text", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("capped_amount", sa.Float(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "appeal_documents",
        _uuid_pk(),
        _fk("claim_id", "claims.id"),
        _fk("model_version_id", "model_versions.id", nullable=True, ondelete="SET NULL"),
        sa.Column("content", sa.Text(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "extracted_facts",
        _uuid_pk(),
        _fk("claim_id", "claims.id"),
        _fk("document_id", "documents.id", nullable=True),
        _fk("chunk_id", "document_chunks.id", nullable=True, ondelete="SET NULL"),
        sa.Column("kind", _enum("fact_kind"), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_number", sa.Float(), nullable=True),
        sa.Column("value_date", sa.String(40), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("extra", postgresql.JSONB(), nullable=True),
        *_timestamps(),
    )

    # --- intelligence -------------------------------------------------------
    op.create_table(
        "ai_decisions",
        _uuid_pk(),
        _fk("claim_id", "claims.id"),
        _fk("model_version_id", "model_versions.id", nullable=True, ondelete="SET NULL"),
        sa.Column("decision_type", sa.String(40), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=True),
        sa.Column("outcome", sa.String(80), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_ai_decisions_decision_type", "ai_decisions", ["decision_type"])

    op.create_table(
        "risk_signals",
        _uuid_pk(),
        _fk("claim_id", "claims.id"),
        _fk("claim_item_id", "claim_items.id", nullable=True, ondelete="SET NULL"),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("direction", _enum("signal_direction"), nullable=False, server_default="AGGRAVATING"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_risk_signals_code", "risk_signals", ["code"])

    op.create_table(
        "risk_scores",
        _uuid_pk(),
        _fk("claim_id", "claims.id"),
        _fk("model_version_id", "model_versions.id", nullable=True, ondelete="SET NULL"),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("band", _enum("risk_band"), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("breakdown", postgresql.JSONB(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "contradictions",
        _uuid_pk(),
        _fk("claim_id", "claims.id"),
        _fk("left_fact_id", "extracted_facts.id", nullable=True, ondelete="SET NULL"),
        _fk("right_fact_id", "extracted_facts.id", nullable=True, ondelete="SET NULL"),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("severity", _enum("risk_band"), nullable=False),
        *_timestamps(),
    )

    # --- human loop ---------------------------------------------------------
    op.create_table(
        "investigations",
        _uuid_pk(),
        _fk("claim_id", "claims.id"),
        _fk("opened_by_id", "users.id", nullable=True, ondelete="SET NULL"),
        _fk("assigned_to_id", "users.id", nullable=True, ondelete="SET NULL"),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", _enum("investigation_status"), nullable=False, server_default="OPEN"),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_investigations_status", "investigations", ["status"])

    op.create_table(
        "investigation_notes",
        _uuid_pk(),
        _fk("investigation_id", "investigations.id"),
        _fk("author_id", "users.id", nullable=True, ondelete="SET NULL"),
        sa.Column("body", sa.Text(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "human_decisions",
        _uuid_pk(),
        _fk("claim_id", "claims.id"),
        _fk("claim_item_id", "claim_items.id", nullable=True, ondelete="SET NULL"),
        _fk("decided_by_id", "users.id", nullable=True, ondelete="SET NULL"),
        _fk("ai_decision_id", "ai_decisions.id", nullable=True, ondelete="SET NULL"),
        sa.Column("action", _enum("decision_action"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("previous_ai_outcome", sa.String(80), nullable=True),
        sa.Column("overrides_ai", sa.Boolean(), nullable=False, server_default="false"),
        *_timestamps(),
    )

    op.create_table(
        "events",
        _uuid_pk(),
        _fk("claim_id", "claims.id"),
        _fk("actor_id", "users.id", nullable=True, ondelete="SET NULL"),
        sa.Column("kind", _enum("event_kind"), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_events_claim_occurred", "events", ["claim_id", "occurred_at"])

    op.create_table(
        "audit_logs",
        _uuid_pk(),
        _fk("actor_id", "users.id", nullable=True, ondelete="SET NULL"),
        _fk("organization_id", "organizations.id", nullable=True, ondelete="SET NULL"),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    # --- remaining single-column indexes ------------------------------------
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_claims_reference", "claims", ["reference"], unique=True)
    op.create_index("ix_claimants_member_id", "claimants", ["member_id"])
    op.create_index("ix_providers_registration_number", "providers", ["registration_number"])
    op.create_index("ix_policies_policy_number", "policies", ["policy_number"])
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    for table, column in FK_INDEXES:
        op.create_index(f"ix_{table}_{column}", table, [column])

    op.execute(AUDIT_LOG_GUARD_FN)
    op.execute(AUDIT_LOG_GUARD_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_append_only ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS claimsense_audit_logs_append_only()")

    for table in [
        "audit_logs", "events", "human_decisions", "investigation_notes", "investigations",
        "contradictions", "risk_scores", "risk_signals", "ai_decisions", "extracted_facts",
        "appeal_documents", "audit_findings", "document_chunks", "document_pages", "documents",
        "claim_items", "claims", "model_versions", "policies", "providers", "claimants",
        "users", "organizations",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    for name in ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {name}")

    # Restore the legacy structure so this revision is reversible. Legacy data is
    # not recoverable; see the module docstring.
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("insurer_name", sa.String(), nullable=False),
        sa.Column("policy_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "policy_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.String(), nullable=True),
        sa.Column("section_header", sa.String(), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
    )

    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_billed", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "claim_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("billed_amount", sa.Float(), nullable=False),
        sa.Column("allowed_amount", sa.Float(), nullable=True),
    )

    op.create_table(
        "audit_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claim_items.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("policy_clause_cited", sa.String(), nullable=True),
        sa.Column("original_clause_text", sa.String(), nullable=True),
        sa.Column("page_number", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "appeal_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
