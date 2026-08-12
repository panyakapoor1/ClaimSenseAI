from pydantic import BaseModel, Field


class ServiceBanner(BaseModel):
    service: str
    version: str
    docs: str


class HealthResponse(BaseModel):
    status: str = Field(examples=["healthy"])
    llm_available: bool = Field(description="Whether a model provider is configured.")
    llm_model: str | None = Field(description="Active model id, or null when unconfigured.")


class DependencyCheck(BaseModel):
    model_config = {"extra": "allow"}

    ok: bool
    error: str | None = None
    required: bool = Field(
        default=True,
        description="Whether readiness fails when this check fails.",
    )


class ReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, DependencyCheck]
