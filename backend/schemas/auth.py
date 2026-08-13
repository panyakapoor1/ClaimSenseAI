import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    organization_id: uuid.UUID
    created_at: datetime.datetime


class SessionOut(BaseModel):
    """The signed-in user and what they are allowed to do.

    Capabilities are returned so the UI can hide controls the caller cannot use.
    This is presentation only; the server enforces the same list independently.
    """

    user: UserOut
    capabilities: list[str]
    expires_in: int = Field(description="Token lifetime in seconds.")
