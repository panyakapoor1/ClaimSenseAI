"""Turning a PDF into pages, passages and geometry.

Three things the prototype did not do:

  1. **OCR fallback.** `pdfplumber` reads embedded text layers only. A scanned or
     photographed bill has none, so extraction returned an empty string and the
     pipeline reported a successful parse of zero line items. Pages with too
     little text are now rasterised and read with Tesseract.

  2. **Geometry.** Every passage records the page and the bounding box it came
     from, which is what lets a citation open its source region later.

  3. **Layout-aware chunking.** Splitting on a regex over raw page text lost the
     association between a heading and the words underneath it. Chunking now
     works from positioned words, so a passage's box is the union of its words.
"""

import io
import logging
import re
from dataclasses import dataclass, field

import pdfplumber

logger = logging.getLogger(__name__)

# Below this many characters a page is treated as having no usable text layer.
# A scanned page usually yields nothing; a handful of stray characters from a
# header or a watermark should not defeat the check.
MIN_TEXT_LAYER_CHARS = 40

# Rendering resolution for OCR. 300 DPI is the usual floor for reliable
# recognition of body text; higher mostly costs time.
OCR_DPI = 300

# Vertical gap, in points, that ends a passage. Roughly 1.5 blank lines at
# typical body sizes — enough to separate blocks without splitting paragraphs.
PARAGRAPH_GAP = 14.0

MAX_CHUNK_CHARS = 1200

HEADER_PATTERN = re.compile(
    r"^(?:"
    r"[A-Z][A-Z0-9\s\-&/,.']{5,}$"          # ALL CAPS headings
    r"|\d+(?:\.\d+)*\.?\s+[A-Z].{0,80}$"     # 4.1 ROOM RENT LIMIT
    r"|(?:Section|Article|Clause|Part)\s+\d+"
    r")"
)


@dataclass
class Word:
    text: str
    x0: float
    top: float
    x1: float
    bottom: float


@dataclass
class ParsedPage:
    page_number: int
    text: str
    width: float
    height: float
    from_ocr: bool
    words: list[Word] = field(default_factory=list)


@dataclass
class Passage:
    """A chunk of text with the geometry needed to highlight it."""

    ordinal: int
    page_number: int
    section_header: str | None
    text: str
    bbox: tuple[float, float, float, float] | None


def _ocr_page(page) -> tuple[str, list[Word]]:
    """Rasterise a page and read it with Tesseract, keeping word boxes.

    Returns empty results rather than raising if OCR is unavailable: a missing
    Tesseract binary should degrade this page to "no text", not fail the whole
    document.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        logger.warning("OCR requested but pytesseract/Pillow are not installed.")
        return "", []

    try:
        image = page.to_image(resolution=OCR_DPI).original
        if not isinstance(image, Image.Image):
            image = Image.open(io.BytesIO(image))

        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except Exception as e:
        logger.warning("OCR failed on page %s: %s", page.page_number, e)
        return "", []

    # Tesseract reports pixel coordinates at OCR_DPI; PDF geometry is in points
    # at 72 per inch. Scaling here keeps every downstream box in PDF space.
    scale = 72.0 / OCR_DPI

    words: list[Word] = []
    for i, raw in enumerate(data["text"]):
        text = raw.strip()
        if not text:
            continue
        try:
            confidence = float(data["conf"][i])
        except (TypeError, ValueError):
            confidence = -1.0
        if confidence < 30:
            continue  # Tesseract's own signal that it is guessing.

        left, top = data["left"][i] * scale, data["top"][i] * scale
        width, height = data["width"][i] * scale, data["height"][i] * scale
        words.append(Word(text, left, top, left + width, top + height))

    return " ".join(w.text for w in words), words


def parse_pdf(payload: bytes) -> list[ParsedPage]:
    """Read every page, using OCR where there is no usable text layer."""
    pages: list[ParsedPage] = []

    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            from_ocr = False
            words: list[Word] = []

            if len(text) >= MIN_TEXT_LAYER_CHARS:
                words = [
                    Word(w["text"], w["x0"], w["top"], w["x1"], w["bottom"])
                    for w in page.extract_words(use_text_flow=True)
                ]
            else:
                logger.info(
                    "Page %s has %s characters of text layer; falling back to OCR.",
                    index, len(text),
                )
                ocr_text, ocr_words = _ocr_page(page)
                if ocr_text:
                    text, words, from_ocr = ocr_text, ocr_words, True

            pages.append(
                ParsedPage(
                    page_number=index,
                    text=text,
                    width=float(page.width),
                    height=float(page.height),
                    from_ocr=from_ocr,
                    words=words,
                )
            )

    return pages


def _group_lines(words: list[Word]) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Collapse positioned words into lines with their bounding boxes."""
    if not words:
        return []

    ordered = sorted(words, key=lambda w: (round(w.top, 1), w.x0))
    lines: list[list[Word]] = [[ordered[0]]]

    for word in ordered[1:]:
        current = lines[-1]
        # Same line when the vertical centres are within half a line height.
        tolerance = max(2.0, (current[-1].bottom - current[-1].top) * 0.6)
        if abs(word.top - current[-1].top) <= tolerance:
            current.append(word)
        else:
            lines.append([word])

    result = []
    for line in lines:
        line.sort(key=lambda w: w.x0)
        result.append((
            " ".join(w.text for w in line),
            (
                min(w.x0 for w in line),
                min(w.top for w in line),
                max(w.x1 for w in line),
                max(w.bottom for w in line),
            ),
        ))
    return result


def chunk_page(page: ParsedPage, start_ordinal: int) -> list[Passage]:
    """Split one page into passages, carrying headings and geometry.

    Falls back to whole-page text when there is no word geometry, so a page
    still contributes a searchable passage even without positions.
    """
    lines = _group_lines(page.words)

    if not lines:
        if not page.text.strip():
            return []
        return [
            Passage(
                ordinal=start_ordinal,
                page_number=page.page_number,
                section_header=None,
                text=page.text.strip(),
                bbox=None,
            )
        ]

    passages: list[Passage] = []
    current_header: str | None = None
    buffer: list[str] = []
    boxes: list[tuple[float, float, float, float]] = []
    ordinal = start_ordinal

    def flush():
        nonlocal buffer, boxes, ordinal
        body = " ".join(buffer).strip()
        if len(body) >= 30:
            passages.append(
                Passage(
                    ordinal=ordinal,
                    page_number=page.page_number,
                    section_header=current_header,
                    text=body,
                    bbox=(
                        min(b[0] for b in boxes),
                        min(b[1] for b in boxes),
                        max(b[2] for b in boxes),
                        max(b[3] for b in boxes),
                    ) if boxes else None,
                )
            )
            ordinal += 1
        buffer, boxes = [], []

    previous_bottom = None

    for text, box in lines:
        stripped = text.strip()
        if not stripped:
            continue

        is_header = bool(HEADER_PATTERN.match(stripped)) and len(stripped) < 90
        gapped = previous_bottom is not None and (box[1] - previous_bottom) > PARAGRAPH_GAP
        too_long = sum(len(b) for b in buffer) > MAX_CHUNK_CHARS

        if is_header or gapped or too_long:
            flush()
            if is_header:
                current_header = stripped
                previous_bottom = box[3]
                continue

        buffer.append(stripped)
        boxes.append(box)
        previous_bottom = box[3]

    flush()
    return passages


def chunk_document(pages: list[ParsedPage]) -> list[Passage]:
    passages: list[Passage] = []
    for page in pages:
        passages.extend(chunk_page(page, start_ordinal=len(passages)))
    return passages


def document_text(pages: list[ParsedPage]) -> str:
    """Whole-document text, page-delimited so the LLM can cite a page."""
    return "\n\n".join(
        f"--- Page {p.page_number} ---\n{p.text}" for p in pages if p.text.strip()
    )
