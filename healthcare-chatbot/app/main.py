"""Entry point for running the FastAPI backend directly.

    python -m app.main
    # or
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import uvicorn

from app.api import app  # noqa: F401  (re-exported for `uvicorn app.main:app`)
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
