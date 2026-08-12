import uuid

from pydantic import BaseModel, ConfigDict, Field

from models.enums import DocumentKind, DocumentStatus, FactKind


class Region(BaseModel):
    """A highlightable rectangle on a page, in PDF points from the top-left.

    Normalised fractions are supplied alongside the raw points so a viewer can
    position an overlay without knowing the page dimensions.
    """

    page_number: int
    x0: float
    y0: float
    x1: float
    y1: float


class FactOut(BaseModel):
    """An extracted value and where it came from.

    There is deliberately no confidence percentage here. The pipeline has no
    calibrated probability for an extracted value, and rendering one would imply
    a precision that does not exist. What it genuinely knows is whether the value
    was found on the page and how.
    """

    id: uuid.UUID
    kind: FactKind
    label: str
    value_text: str | None
    value_number: float | None
    value_date: str | None
    located: bool
    match: str | None = Field(
        default=None,
        description=(
            "How the value was tied to the page: EXACT_PHRASE (every word matched "
            "in order), NUMERIC_FORM (an amount matched one of its printed forms), "
            "or PARTIAL_TOKEN (only the most distinctive word matched). Null when "
            "the value was not located."
        ),
    )
    region: Region | None


class DocumentPageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    width: float | None
    height: float | None
    from_ocr: bool = Field(
        description="True when this page had no text layer and was read by OCR."
    )
    char_count: int


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: DocumentKind
    status: DocumentStatus
    filename: str
    byte_size: int
    page_count: int | None
    parse_error: str | None
    ocr_page_count: int = Field(
        default=0, description="How many pages required OCR."
    )
    pages: list[DocumentPageOut] = []


class EvidenceResponse(BaseModel):
    claim_id: uuid.UUID
    documents: list[DocumentOut]
    facts: list[FactOut]
