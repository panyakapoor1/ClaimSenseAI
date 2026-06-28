import pdfplumber
import re
from sentence_transformers import SentenceTransformer

# Lazy load the model to prevent blocking async event loops during import
embedding_model = None


def extract_policy_text(pdf_path: str) -> list[dict]:
    """Extract text from a policy PDF and chunk it by page with section detection."""
    chunks = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text or len(text.strip()) < 50:
                continue

            # Split page text into sections by detecting header-like patterns
            # Common patterns: ALL CAPS lines, numbered sections (1., 2., etc.)
            sections = _split_into_sections(text)

            for section_header, section_text in sections:
                if len(section_text.strip()) < 30:
                    continue
                chunks.append({
                    "page_number": str(i + 1),
                    "section_header": section_header or f"Page {i + 1}",
                    "text_content": section_text.strip()
                })

    return chunks


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split a page of text into (header, body) tuples using heuristic patterns."""
    # Pattern: Lines that are ALL CAPS, or start with a number followed by a period
    header_pattern = re.compile(
        r"^(?:"
        r"[A-Z][A-Z\s\-&]{5,}$"       # ALL CAPS headers (min 6 chars)
        r"|"
        r"\d+\.\s+[A-Z].*$"            # Numbered sections like "1. DEFINITIONS"
        r"|"
        r"(?:Section|Article|Clause)\s+\d+"  # Explicit section markers
        r")",
        re.MULTILINE
    )

    matches = list(header_pattern.finditer(text))

    if not matches:
        return [(None, text)]

    sections = []
    for i, match in enumerate(matches):
        header = match.group().strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((header, body))

    # Capture any text before the first header
    if matches[0].start() > 0:
        preamble = text[:matches[0].start()].strip()
        if len(preamble) > 30:
            sections.insert(0, ("Preamble", preamble))

    return sections


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate 384-dimensional embeddings for a list of text chunks."""
    global embedding_model
    if embedding_model is None:
        print("Loading embedding model...")
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("Model loaded.")
    embeddings = embedding_model.encode(texts, show_progress_bar=True)
    return embeddings.tolist()
