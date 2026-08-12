"""Minimal PDF builders.

Written by hand rather than with a PDF library so the image does not carry an
authoring dependency, and so generated documents are byte-for-byte deterministic.

Used by the seed script to produce real demo documents — a bill the pipeline
actually parses — and by the tests for the same reason.
""" 

import io

# Sample content, used by tests. Callers pass their own lines.
BILL_LINES = [
    "SUNRISE MULTISPECIALITY HOSPITAL",
    "Patient: Ananya Rao",
    "ROOM RENT",
    "Shared room 3 days 13500",
    "SURGEON FEES",
    "Laparoscopic appendectomy 62000",
    "PHARMACY",
    "Post-operative antibiotics 6400",
]


def _escape(line: str) -> str:
    return line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _page_content(lines: list[str]) -> bytes:
    """A content stream drawing one page of text."""
    ops = ["BT", "/F1 11 Tf", "60 790 Td", "16 TL"]
    for index, line in enumerate(lines):
        text = f"({_escape(line)}) Tj"
        ops.append(text if index == 0 else f"T* {text}")
    ops.append("ET")
    return "\n".join(ops).encode("latin-1")


def text_layer_pdf(lines: list[str] | None = None, *, lines_per_page: int = 46) -> bytes:
    """A PDF with a real, extractable text layer, paginated as needed.

    Object offsets are computed as the file is assembled, so the xref table is
    correct and strict parsers accept it. Multi-page support matters because a
    realistic policy runs to dozens of clauses, and a document whose every clause
    claims to be on page 1 makes page citations meaningless.
    """
    lines = lines if lines is not None else BILL_LINES

    pages = [
        lines[start : start + lines_per_page]
        for start in range(0, max(len(lines), 1), lines_per_page)
    ] or [[]]

    # Object numbering: 1 catalog, 2 pages, 3 font, then per page a page object
    # followed by its content stream.
    font_number = 3
    first_page_object = 4
    page_numbers = [first_page_object + i * 2 for i in range(len(pages))]

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            "<< /Type /Pages /Kids [{}] /Count {} >>".format(
                " ".join(f"{n} 0 R" for n in page_numbers), len(pages)
            ).encode()
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    for index, page_lines in enumerate(pages):
        content = _page_content(page_lines)
        content_number = page_numbers[index] + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Contents {content_number} 0 R "
                f"/Resources << /Font << /F1 {font_number} 0 R >> >> >>"
            ).encode()
        )
        objects.append(
            b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
            + content + b"\nendstream"
        )

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")

    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")

    xref_at = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())

    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
        + f"startxref\n{xref_at}\n%%EOF\n".encode()
    )
    return out.getvalue()


def image_only_pdf(lines: list[str] | None = None) -> bytes:
    """A PDF whose only content is a rasterised image of text.

    `extract_text()` returns nothing for this, so it is the fixture that proves
    the OCR fallback actually runs. Rendered large: the default bitmap font is
    tiny, and OCR on small glyphs is unreliable for reasons unrelated to the
    pipeline being tested.
    """
    from PIL import Image, ImageDraw, ImageFont

    lines = lines or BILL_LINES

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except OSError:
        font = ImageFont.load_default()

    image = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(image)

    y = 150
    for line in lines:
        draw.text((120, y), line, fill="black", font=font)
        y += 90

    buffer = io.BytesIO()
    image.save(buffer, format="PDF", resolution=200.0)
    return buffer.getvalue()
