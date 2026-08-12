"""Password hashing and session tokens.

Kept free of framework and database imports so it can be unit-tested and reused
from the seed script without pulling in the app.
"""

import datetime
import os
import secrets

import bcrypt
import jwt

ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = datetime.timedelta(hours=12)

# bcrypt silently truncates at 72 bytes. Rejecting longer input is better than
# accepting a password whose tail never affects the hash.
MAX_PASSWORD_BYTES = 72

SESSION_COOKIE = "claimsense_session"


def _load_secret() -> str:
    """The signing key, from the environment.

    A generated fallback is used only when nothing is configured, and it changes
    on every restart — so tokens stop validating and the problem surfaces
    immediately rather than shipping a known default key to production.
    """
    configured = os.getenv("JWT_SECRET", "").strip()
    if configured:
        return configured

    print(
        "WARNING: JWT_SECRET is not set. Using an ephemeral key; all sessions "
        "will be invalidated on restart. Set JWT_SECRET in backend/.env."
    )
    return secrets.token_urlsafe(48)


SECRET_KEY = _load_secret()


class InvalidToken(Exception):
    """The token is absent, malformed, expired or not signed by us."""


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password exceeds {MAX_PASSWORD_BYTES} bytes.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str | None) -> bool:
    """Constant-time check that tolerates a missing hash.

    Users seeded before credentials existed have no hash. Returning False rather
    than raising means such an account simply cannot log in.
    """
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(*, user_id: str, organization_id: str, role: str) -> tuple[str, int]:
    """Return a signed token and its lifetime in seconds.

    The role is embedded so routine authorisation needs no database round trip.
    The trade-off is that a role change only takes effect on the next login;
    the short TTL bounds that window.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    expires = now + ACCESS_TOKEN_TTL
    payload = {
        "sub": user_id,
        "org": organization_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, int(ACCESS_TOKEN_TTL.total_seconds())


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise InvalidToken("Your session has expired. Please sign in again.") from e
    except jwt.InvalidTokenError as e:
        raise InvalidToken("Invalid session token.") from e
