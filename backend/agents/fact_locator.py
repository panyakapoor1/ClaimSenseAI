"""Binding extracted values back to where they appear on the page.

The LLM returns structured values but no positions. Rather than ask it for
coordinates (which it would invent), the value is searched for in the parsed
word geometry. A fact whose text cannot be found on any page gets no box and is
reported with lower confidence, which is honest: we know what was extracted but
not where it came from.
"""

import enum
import re
from dataclasses import dataclass

from agents.document_parser import ParsedPage, Word


class MatchKind(str, enum.Enum):
    """How a value was tied to the page.

    Reported instead of a confidence score. The locator knows exactly how it
    matched, and saying so is more useful, and more honest, than mapping that
    onto a number that looks like a calibrated probability and is not.
    """

    EXACT_PHRASE = "EXACT_PHRASE"      # every word matched, in order
    NUMERIC_FORM = "NUMERIC_FORM"      # an amount matched one of its printed forms
    PARTIAL_TOKEN = "PARTIAL_TOKEN"    # only the most distinctive word matched


@dataclass
class Location:
    page_number: int
    bbox: tuple[float, float, float, float]
    kind: MatchKind = MatchKind.EXACT_PHRASE


def _normalise(text: str) -> str:
    """Comparable form: casefolded, punctuation-light, single-spaced."""
    return re.sub(r"[^a-z0-9. ]+", " ", text.casefold()).strip()


def _number_forms(value: float) -> list[str]:
    """The ways an amount plausibly appears in a bill.

    A billed amount of 13500.0 might be printed as "13500", "13,500",
    "13500.00" or "13,500.00", so all are tried before giving up.
    """
    whole = int(value) if float(value).is_integer() else None
    forms = []
    if whole is not None:
        forms += [f"{whole}", f"{whole:,}"]
    forms += [f"{value:.2f}", f"{value:,.2f}"]
    return forms


def _span_box(words: list[Word]) -> tuple[float, float, float, float]:
    return (
        min(w.x0 for w in words),
        min(w.top for w in words),
        max(w.x1 for w in words),
        max(w.bottom for w in words),
    )


def locate_text(pages: list[ParsedPage], needle: str) -> Location | None:
    """Find a phrase in the document and return its page and box.

    Matches on a sliding window of words so that a multi-word phrase resolves to
    the span covering all of them, not just the first word.
    """
    target = _normalise(needle)
    if not target:
        return None

    target_tokens = target.split()
    if not target_tokens:
        return None

    for page in pages:
        if not page.words:
            continue

        normalised = [_normalise(w.text) for w in page.words]

        for start in range(len(page.words)):
            if normalised[start] != target_tokens[0]:
                continue
            end = start + len(target_tokens)
            if end > len(page.words):
                continue
            if normalised[start:end] == target_tokens:
                return Location(
                    page.page_number,
                    _span_box(page.words[start:end]),
                    MatchKind.EXACT_PHRASE,
                )

    # Fall back to the longest distinctive token, so a description that was
    # reworded by the model still anchors somewhere sensible.
    distinctive = max(target_tokens, key=len)
    if len(distinctive) >= 5:
        for page in pages:
            for index, word in enumerate(page.words):
                if _normalise(word.text) == distinctive:
                    return Location(
                        page.page_number,
                        _span_box([page.words[index]]),
                        MatchKind.PARTIAL_TOKEN,
                    )

    return None


def locate_amount(pages: list[ParsedPage], value: float) -> Location | None:
    for form in _number_forms(value):
        found = locate_text(pages, form)
        if found:
            found.kind = MatchKind.NUMERIC_FORM
            return found
    return None
