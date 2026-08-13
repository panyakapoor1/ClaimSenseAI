"""One finding per line item

The ORM declares `ClaimItem.audit_finding` as `uselist=False`, but nothing in the
database enforced it. Re-auditing a claim therefore inserted a second finding for
every line, and SQLAlchemy would silently return whichever one it loaded first,
so a claim could hold two contradictory verdicts and display them at random.

The unique constraint makes duplicate verdicts impossible rather than merely
discouraged, which is what lets the audit task be safely re-runnable.

Any pre-existing duplicates are resolved by keeping the most recent finding for
each item, since that is the verdict the last completed audit reached.

Revision ID: c9f1b3e75d20
Revises: b7e2d4a91c58
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c9f1b3e75d20"
down_revision: Union[str, None] = "b7e2d4a91c58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM audit_findings a
        USING audit_findings b
        WHERE a.claim_item_id = b.claim_item_id
          AND (a.created_at, a.id) < (b.created_at, b.id)
        """
    )
    op.create_unique_constraint(
        "uq_audit_findings_claim_item_id", "audit_findings", ["claim_item_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_audit_findings_claim_item_id", "audit_findings", type_="unique"
    )
