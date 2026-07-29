"""Pydantic schemas shared by the API, RAG pipeline, and memory store.

Centralising these avoids circular imports between `api.py` and the
modules it orchestrates, and gives FastAPI automatic request validation
plus OpenAPI documentation for free.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Role(str, Enum):
    """Speaker role for a single turn in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class GuardrailFlag(str, Enum):
    """Safety categories the guardrail layer can raise on a message.

    See app/guardrails.py for the detection rules. Blocking categories
    (emergencies, injection attempts, illegal-drug requests) short-circuit
    the LLM call entirely; the rest are advisory flags the LLM is expected
    to redirect around per the system prompt.
    """

    DIAGNOSIS_REQUEST = "diagnosis_request"
    MEDICATION_DOSAGE = "medication_dosage"
    PRESCRIPTION_REQUEST = "prescription_request"
    ILLEGAL_DRUG_ADVICE = "illegal_drug_advice"
    MENTAL_HEALTH_CRISIS = "mental_health_crisis"
    MEDICAL_EMERGENCY = "medical_emergency"
    PROMPT_INJECTION = "prompt_injection"
    PROMPT_LEAK_ATTEMPT = "prompt_leak_attempt"


class ChatMessage(BaseModel):
    """A single stored turn in a conversation's history."""

    role: Role
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourceDocument(BaseModel):
    """A knowledge-base chunk retrieved by RAG, returned as a citation."""

    title: str
    source: str
    snippet: str
    score: Optional[float] = Field(default=None, description="Cosine similarity to the query, 0-1.")


class ChatRequest(BaseModel):
    """Payload for POST /chat."""

    session_id: Optional[str] = Field(
        default=None, description="Existing session id. A new one is created if omitted."
    )
    message: str = Field(..., min_length=1, max_length=2000)
    language: Optional[str] = Field(
        default="en", description="ISO language code the user prefers for the reply."
    )


class ChatResponse(BaseModel):
    """Response body for POST /chat."""

    session_id: str
    response: str
    disclaimer: str
    sources: list[SourceDocument] = Field(default_factory=list)
    guardrail_flags: list[GuardrailFlag] = Field(default_factory=list)
    is_emergency: bool = False
    latency_ms: float = Field(description="Total server-side processing time for this request.")


class ClearRequest(BaseModel):
    session_id: str


class ClearResponse(BaseModel):
    session_id: str
    cleared: bool = Field(description="True if a session with this id existed and was cleared.")


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    llm_provider: str
    rag_enabled: bool
    vectorstore_loaded: bool


def new_session_id() -> str:
    """Generate a fresh opaque session identifier."""
    return str(uuid.uuid4())
