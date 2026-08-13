"""Document storage.

Documents used to be written to a container-local directory and deleted once
parsed, which meant a finding could cite page 4 of a bill nobody could open
again. Evidence has to outlive the job that read it.

S3-compatible so the same code addresses MinIO locally and a managed bucket
later. Falls back to the local filesystem when no endpoint is configured, so the
app still runs for anyone who has not started MinIO; the fallback announces
itself rather than failing silently.
"""

import logging
import os
import pathlib
import threading

logger = logging.getLogger(__name__)

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "").strip()
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "").strip()
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "").strip()
S3_BUCKET = os.getenv("S3_BUCKET", "claimsense-documents").strip()

LOCAL_ROOT = pathlib.Path(os.getenv("LOCAL_STORAGE_ROOT", "uploads"))

USING_OBJECT_STORAGE = bool(S3_ENDPOINT_URL and S3_ACCESS_KEY and S3_SECRET_KEY)

_client = None
_client_lock = threading.Lock()
_bucket_ready = False


class StorageError(RuntimeError):
    """Reading or writing a document failed."""


def _s3():
    """Lazily build the S3 client and ensure the bucket exists.

    Built on first use rather than at import so that a missing or slow MinIO
    does not block application startup.
    """
    global _client, _bucket_ready

    with _client_lock:
        if _client is None:
            import boto3
            from botocore.config import Config

            _client = boto3.client(
                "s3",
                endpoint_url=S3_ENDPOINT_URL,
                aws_access_key_id=S3_ACCESS_KEY,
                aws_secret_access_key=S3_SECRET_KEY,
                config=Config(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            )

        if not _bucket_ready:
            from botocore.exceptions import ClientError

            try:
                _client.head_bucket(Bucket=S3_BUCKET)
            except ClientError:
                try:
                    _client.create_bucket(Bucket=S3_BUCKET)
                    logger.info("Created object storage bucket %s", S3_BUCKET)
                except ClientError as e:
                    # Another worker may have created it in the meantime.
                    if e.response.get("Error", {}).get("Code") not in (
                        "BucketAlreadyOwnedByYou",
                        "BucketAlreadyExists",
                    ):
                        raise
            _bucket_ready = True

    return _client


def put(key: str, payload: bytes, *, content_type: str = "application/pdf") -> str:
    """Store bytes under `key` and return the key."""
    if USING_OBJECT_STORAGE:
        try:
            _s3().put_object(
                Bucket=S3_BUCKET, Key=key, Body=payload, ContentType=content_type
            )
            return key
        except Exception as e:
            raise StorageError(f"Could not store document {key}: {e}") from e

    path = LOCAL_ROOT / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return key


def get(key: str) -> bytes:
    """Read the bytes stored under `key`."""
    if USING_OBJECT_STORAGE:
        try:
            return _s3().get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()
        except Exception as e:
            raise StorageError(f"Could not read document {key}: {e}") from e

    path = LOCAL_ROOT / key
    if not path.exists():
        # Tolerates keys written before object storage existed, which were
        # stored with the `uploads/` prefix already in the key.
        legacy = pathlib.Path(key)
        if legacy.exists():
            return legacy.read_bytes()
        raise StorageError(f"Document {key} is not in storage.")
    return path.read_bytes()


def exists(key: str) -> bool:
    if USING_OBJECT_STORAGE:
        try:
            _s3().head_object(Bucket=S3_BUCKET, Key=key)
            return True
        except Exception:
            return False
    return (LOCAL_ROOT / key).exists() or pathlib.Path(key).exists()


def describe() -> dict:
    """Backend description, for /ready and for labelling degraded mode."""
    return {
        "backend": "s3" if USING_OBJECT_STORAGE else "local-filesystem",
        "endpoint": S3_ENDPOINT_URL or str(LOCAL_ROOT),
        "bucket": S3_BUCKET if USING_OBJECT_STORAGE else None,
    }
