import os
from groq import AsyncGroq

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# We use an async client because we want non-blocking calls inside the worker
groq_client = AsyncGroq(api_key=GROQ_API_KEY if GROQ_API_KEY else "dummy_key_to_prevent_import_error")
