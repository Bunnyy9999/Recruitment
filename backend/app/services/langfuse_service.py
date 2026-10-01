from __future__ import annotations

from typing import Any

from langfuse import Langfuse

from backend.app.config import settings


def build_langfuse_client() -> Any | None:
    public_key = (settings.langfuse_public_key or "").strip()
    secret_key = ""
    if settings.langfuse_secret_key is not None:
        secret_key = settings.langfuse_secret_key.get_secret_value().strip()
    base_url = str(settings.langfuse_base_url).strip() if settings.langfuse_base_url else ""

    if not public_key or not secret_key or not base_url:
        return None

    try:
        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=base_url,
            tracing_enabled=True,
            debug=False,
            environment="recruitment-tool",
        )
    except Exception:
        return None
