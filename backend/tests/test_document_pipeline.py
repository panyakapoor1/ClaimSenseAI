"""The document pipeline: storage, OCR fallback, chunking and provenance.

The OCR test builds a genuinely image-only PDF (a rendered bill with no text
layer at all) because that is the case the prototype failed silently on. A
fixture with an embedded text layer would pass without OCR ever running.
"""

import io

import pytest

from agents.document_parser import (
    MIN_TEXT_LAYER_CHARS,
    chunk_document,
    document_text,
    parse_pdf,
)
from agents.fact_locator import locate_amount, locate_text
from services import storage

pytestmark = pytest.mark.asyncio


from tests.pdf_fixtures import image_only_pdf, text_layer_pdf


# --- storage ---------------------------------------------------------------

async def test_storage_round_trip():
    key = "tests/round-trip.bin"
    payload = b"%PDF-1.4 evidence bytes"

    storage.put(key, payload)
    assert storage.get(key) == payload
    assert storage.exists(key) is True


async def test_storage_reports_its_backend():
    described = storage.describe()
    assert described["backend"] in ("s3", "local-filesystem")
    assert described["endpoint"]


async def test_missing_document_raises_rather_than_returning_empty():
    """A lost document must be an error, not an empty parse."""
    with pytest.raises(storage.StorageError):
        storage.get("tests/definitely-not-here.pdf")


# --- parsing ---------------------------------------------------------------

async def test_scanned_pdf_has_no_usable_text_layer():
    """Establishes that the OCR fixture really is image-only."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(image_only_pdf())) as pdf:
        raw = (pdf.pages[0].extract_text() or "").strip()

    assert len(raw) < MIN_TEXT_LAYER_CHARS, (
        f"fixture has a text layer ({len(raw)} chars); it would not exercise OCR"
    )


async def test_ocr_reads_a_scanned_bill():
    """The gate: an image-only bill produces text and is flagged as OCR-derived."""
    pages = parse_pdf(image_only_pdf())

    assert len(pages) == 1
    page = pages[0]

    assert page.from_ocr is True, "an image-only page must be read via OCR"
    assert page.text.strip(), "OCR produced no text at all"
    assert page.words, "OCR produced no positioned words"

    # Recognition is imperfect on a synthetic bitmap; require that it found a
    # meaningful amount of content rather than exact strings.
    assert len(page.text) > 40


async def test_text_layer_pages_are_not_marked_as_ocr():
    pages = parse_pdf(text_layer_pdf())
    assert pages[0].from_ocr is False
    assert "SUNRISE" in pages[0].text.upper()


async def test_pages_carry_dimensions():
    pages = parse_pdf(text_layer_pdf())
    assert pages[0].width > 0 and pages[0].height > 0


# --- chunking --------------------------------------------------------------

async def test_chunks_carry_page_and_bounding_box():
    passages = chunk_document(parse_pdf(text_layer_pdf()))

    assert passages, "no passages produced"
    for passage in passages:
        assert passage.page_number == 1
        assert passage.bbox is not None, f"passage {passage.ordinal} has no geometry"
        x0, y0, x1, y1 = passage.bbox
        assert x1 > x0 and y1 > y0, "bounding box must have positive area"


async def test_chunk_ordinals_are_unique_and_sequential():
    passages = chunk_document(parse_pdf(text_layer_pdf()))
    ordinals = [p.ordinal for p in passages]
    assert ordinals == sorted(ordinals)
    assert len(set(ordinals)) == len(ordinals)


async def test_document_text_is_page_delimited():
    text = document_text(parse_pdf(text_layer_pdf()))
    assert "--- Page 1 ---" in text


# --- provenance ------------------------------------------------------------

async def test_amount_resolves_to_a_region():
    pages = parse_pdf(text_layer_pdf())
    located = locate_amount(pages, 13500.0)

    assert located is not None, "a printed amount must be locatable"
    assert located.page_number == 1
    x0, y0, x1, y1 = located.bbox
    assert x1 > x0 and y1 > y0


async def test_amount_handles_thousands_separators():
    """Bills print 13,500 as often as 13500."""
    from agents.fact_locator import _number_forms

    assert "13,500" in _number_forms(13500.0)
    assert "13500" in _number_forms(13500.0)


async def test_phrase_resolves_to_a_span_covering_all_words():
    pages = parse_pdf(text_layer_pdf())
    single = locate_text(pages, "Laparoscopic")
    phrase = locate_text(pages, "Laparoscopic appendectomy")

    assert single and phrase
    assert phrase.bbox[2] > single.bbox[2], "phrase box must extend past one word"


async def test_absent_value_reports_no_location():
    """Never invent a position for something that is not on the page."""
    pages = parse_pdf(text_layer_pdf())
    assert locate_amount(pages, 999999.0) is None
    assert locate_text(pages, "Zygomatic reconstruction") is None
