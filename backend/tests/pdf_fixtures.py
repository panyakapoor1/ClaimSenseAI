"""Minimal PDF builders for tests.

Written by hand rather than with a PDF library so the production image does not
carry an authoring dependency that only tests need, and so the fixtures are
byte-for-byte deterministic.
"""

import io

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


def text_layer_pdf(lines: list[str] | None = None) -> bytes:
    """A single-page PDF with a real, extractable text layer.

    Object offsets are computed as the file is assembled, so the xref table is
    correct and strict parsers accept it.
    """
    lines = lines or BILL_LINES

    content_lines = ["BT", "/F1 12 Tf", "70 780 Td", "14 TL"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        # First line is placed by Td; subsequent lines advance with T*.
        content_lines.append(f"({escaped}) Tj" if index == 0 else f"T* ({escaped}) Tj")
        if index > 0:
            continue
        content_lines.append("T*")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

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
