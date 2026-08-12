"""Shared response envelopes."""

import base64
import binascii
import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable error identifier.")
    message: str = Field(description="Human-readable explanation.")
    details: object | None = Field(default=None, description="Optional structured context.")
    request_id: str | None = Field(default=None, description="Correlates with server logs.")


class ErrorResponse(BaseModel):
    """The single error shape every failing endpoint returns."""

    error: ErrorDetail


class Page(BaseModel, Generic[T]):
    """A cursor-paginated slice.

    Cursor rather than offset: claims are ordered newest-first and new ones
    arrive while a user is paging, which makes OFFSET silently skip or repeat
    rows. A cursor anchored on (created_at, id) is stable under insertion.
    """

    items: list[T]
    next_cursor: str | None = Field(
        default=None,
        description="Pass as `cursor` to fetch the following page. Null on the last page.",
    )
    has_more: bool = Field(description="Whether a further page exists.")


def encode_cursor(created_at: datetime.datetime, row_id) -> str:
    """Opaque cursor over the sort key.

    Encoded rather than exposed as raw columns so clients treat it as a token
    and do not build queries on its internals, leaving the sort key free to
    change later.
    """
    raw = f"{created_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime.datetime, str]:
    """Reverse of `encode_cursor`. Raises ValueError on anything malformed."""
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        timestamp, row_id = raw.split("|", 1)
        return datetime.datetime.fromisoformat(timestamp), row_id
    except (ValueError, UnicodeDecodeError, binascii.Error) as e:
        raise ValueError(f"Malformed cursor: {cursor}") from e


class JobAccepted(BaseModel):
    """Returned when work is handed to the background queue rather than done inline."""

    status: str = Field(default="processing", examples=["processing"])
    job_id: str = Field(description="Subscribe at /ws/tasks/{job_id} for live progress.")
