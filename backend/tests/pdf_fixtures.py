"""PDF fixtures for tests.

Re-exported from `core.pdf_builder` so tests and the seed script generate
documents the same way — a fixture that diverges from what the app produces
stops testing the real thing.
"""

from core.pdf_builder import BILL_LINES, image_only_pdf, text_layer_pdf

__all__ = ["BILL_LINES", "image_only_pdf", "text_layer_pdf"]
