import os

from groq import AsyncGroq

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Centralised so a provider deprecation is a config change rather than a sweep
# across every agent module. Groq has already retired two model ids under us.
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

LLM_AVAILABLE = bool(GROQ_API_KEY)


class LLMUnavailableError(RuntimeError):
    """Raised when a reasoning step runs without a configured LLM provider.

    This is deliberately fatal rather than mocked. A fabricated audit verdict is
    indistinguishable from a real one once it reaches the findings table, so the
    pipeline stops and says so instead of inventing an answer.
    """


# We use an async client because we want non-blocking calls inside the worker.
groq_client = AsyncGroq(api_key=GROQ_API_KEY) if LLM_AVAILABLE else None


def require_llm() -> AsyncGroq:
    """Return the LLM client, or fail loudly with an operator-actionable message."""
    if groq_client is None:
        raise LLMUnavailableError(
            "No GROQ_API_KEY is configured, so AI reasoning is unavailable. "
            "Set GROQ_API_KEY in backend/.env and restart the worker."
        )
    return groq_client
