from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, Enum, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin, fk, pk
from .enums import DocumentKind, DocumentStatus, FactKind

# all-MiniLM-L6-v2. Kept as a named constant because the column width and the
# model are a matched pair; changing one without the other silently breaks
# retrieval rather than raising.
EMBEDDING_DIM = 384


class Document(Base, TimestampMixin):
    """A source file, and the unit every piece of evidence traces back to.

    Replaces the prototype's approach of writing the upload to a container-local
    path and deleting it after parsing, which made it impossible to re-open the
    page a finding was based on.
    """

    __tablename__ = "documents"

    id = pk()
    organization_id = fk("organizations.id")
    claim_id = fk("claims.id", nullable=True)
    policy_id = fk("policies.id", nullable=True)

    kind = Column(Enum(DocumentKind, name="document_kind", native_enum=True), nullable=False)
    status = Column(
        Enum(DocumentStatus, name="document_status", native_enum=True),
        nullable=False,
        server_default=DocumentStatus.UPLOADED.value,
    )

    filename = Column(String(500), nullable=False)
    content_type = Column(String(120), nullable=False, server_default="application/pdf")
    byte_size = Column(Integer, nullable=False, server_default="0")

    # Object-store key. P4 moves the bytes to MinIO; until then this holds the
    # local path so the column's meaning does not change when storage does.
    storage_key = Column(String(1000), nullable=False)

    # Content hash, so re-uploading the same file is detectable rather than
    # silently creating a second claim.
    checksum_sha256 = Column(String(64), nullable=True, index=True)

    page_count = Column(Integer, nullable=True)
    parse_error = Column(Text, nullable=True)

    claim = relationship("Claim", back_populates="documents")
    policy = relationship("Policy", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base, TimestampMixin):
    """One page of extracted text, with the geometry needed to highlight it."""

    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number", name="uq_document_pages_page"),)

    id = pk()
    document_id = fk("documents.id")

    page_number = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False, server_default="")
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)

    # True when the text came from OCR rather than an embedded text layer, so a
    # low-confidence extraction can be explained rather than just looking wrong.
    from_ocr = Column(Boolean, nullable=False, server_default="false")

    document = relationship("Document", back_populates="pages")


class DocumentChunk(Base, TimestampMixin):
    """A retrievable passage.

    Generalises the prototype's `policy_chunks`: chunks now hang off a document
    rather than a policy, so bills and discharge summaries become searchable on
    the same path in P5 without a second retrieval implementation.
    """

    __tablename__ = "document_chunks"

    id = pk()
    document_id = fk("documents.id")
    policy_id = fk("policies.id", nullable=True)

    ordinal = Column(Integer, nullable=False, server_default="0")
    page_number = Column(Integer, nullable=True, index=True)
    section_header = Column(String(500), nullable=True)
    text_content = Column(Text, nullable=False)

    # Bounding box on the page, for jump-to-source highlighting. Nullable because
    # the current text-layer extractor does not produce geometry; P4 does.
    bbox_x0 = Column(Float, nullable=True)
    bbox_y0 = Column(Float, nullable=True)
    bbox_x1 = Column(Float, nullable=True)
    bbox_y1 = Column(Float, nullable=True)

    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)

    document = relationship("Document", back_populates="chunks")
    policy = relationship("Policy", back_populates="chunks")


class ExtractedFact(Base, TimestampMixin):
    """A structured value pulled from a document, bound to where it came from.

    This is the table that makes "FACT / SOURCE / CONFIDENCE" possible instead of
    an opaque AI summary.
    """

    __tablename__ = "extracted_facts"

    id = pk()
    claim_id = fk("claims.id")
    document_id = fk("documents.id", nullable=True)
    chunk_id = fk("document_chunks.id", nullable=True, ondelete="SET NULL")

    kind = Column(Enum(FactKind, name="fact_kind", native_enum=True), nullable=False)
    label = Column(String(300), nullable=False)
    value_text = Column(Text, nullable=True)
    value_number = Column(Float, nullable=True)
    value_date = Column(String(40), nullable=True)

    page_number = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=False, server_default="0")

    # Free-form provenance from the extractor (prompt version, raw span, etc).
    extra = Column(JSONB, nullable=True)

    claim = relationship("Claim", back_populates="facts")
