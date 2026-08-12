"""Full-text search on document chunks

Adds a generated tsvector column and a GIN index so passages can be searched
lexically as well as semantically.

Embeddings are weak exactly where insurance language is strongest: an exact
clause number ("4.1"), a procedure code, or a rare term like "cholecystectomy"
carries almost no distinguishing signal in a 384-dimensional average, but is a
precise lexical match. Hybrid retrieval covers both.

The column is GENERATED ALWAYS, so it cannot drift from the text it indexes —
there is no application code that could forget to update it.

Revision ID: b7e2d4a91c58
Revises: a1c4e7b93f21
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7e2d4a91c58"
down_revision: Union[str, None] = "a1c4e7b93f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The section header is weighted above the body: a query naming a clause should
# rank that clause first, even when the phrase also appears in prose elsewhere.
TSVECTOR_EXPRESSION = (
    "setweight(to_tsvector('english', coalesce(section_header, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(text_content, '')), 'B')"
)


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE document_chunks
        ADD COLUMN text_search tsvector
        GENERATED ALWAYS AS ({TSVECTOR_EXPRESSION}) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_text_search "
        "ON document_chunks USING GIN (text_search)"
    )

    # Supports the vector scan. Lists is tuned for a small corpus; an IVFFlat
    # index with too many lists on few rows degrades recall badly.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding "
        "ON document_chunks USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 10)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_text_search")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS text_search")
