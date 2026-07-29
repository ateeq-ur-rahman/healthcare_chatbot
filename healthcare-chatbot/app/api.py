"""FastAPI application: HTTP layer and request orchestration.

A single chat turn flows through:

    1. Resolve session_id (existing or newly minted)
    2. Input guardrails on the raw message
       -> if blocked (emergency / injection / illegal request), return the
          deterministic override response immediately and skip the LLM
    3. RAG retrieval of top-k relevant knowledge-base chunks
    4. Prompt assembly (system + retrieved context + history)
    5. LLM call (provider-abstracted, retried on transient failure)
    6. Output guardrails on the LLM's text, sanitizing if needed
    7. Persist both turns to conversation memory
    8. Return a structured ChatResponse (response + disclaimer + sources)

See app/guardrails.py, app/rag.py, app/prompts.py, and app/llm.py for the
individual stages.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import guardrails, rag
from app.config import settings
from app.guardrails import GuardrailResult
from app.llm import BaseLLMClient, get_llm_client
from app.memory import MemoryStore, get_memory_store
from app.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ClearRequest,
    ClearResponse,
    GuardrailFlag,
    HealthResponse,
    HistoryResponse,
    Role,
    SourceDocument,
    new_session_id,
)
from app.prompts import MEDICAL_DISCLAIMER, SYSTEM_PROMPT, build_user_turn
from app.utils import get_logger, stopwatch

logger = get_logger(__name__)

# FastAPI dependency aliases - these wrap the process-wide singletons from
# memory.py / llm.py so routes ask for "a memory store" / "an LLM client"
# rather than reaching into module globals directly. That's what lets
# individual endpoints be tested with a fake store/client via
# `app.dependency_overrides` without needing to install a real API key.
MemoryStoreDep = Annotated[MemoryStore, Depends(get_memory_store)]
LLMClientDep = Annotated[BaseLLMClient, Depends(get_llm_client)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("app_starting", extra={"environment": settings.environment, "provider": settings.llm_provider})
    if settings.rag_enabled:
        try:
            rag.get_vector_store()
        except Exception as exc:
            # A cold-start indexing failure shouldn't crash the whole app -
            # requests will just get empty RAG context until it's fixed.
            logger.error("vectorstore_init_failed", extra={"error": str(exc)})
    yield
    logger.info("app_shutting_down")


app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered healthcare information chatbot. Educational use only — "
        "not a substitute for professional medical advice."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _retrieve_sources(session_id: str, message: str) -> list[SourceDocument]:
    """RAG retrieval, degrading to no citations rather than failing the request."""
    try:
        sources = rag.retrieve(message)
    except Exception as exc:
        logger.error("rag_retrieval_failed", extra={"session_id": session_id, "error": str(exc)})
        return []
    logger.info(
        "rag_retrieved_documents",
        extra={"session_id": session_id, "num_sources": len(sources), "sources": [s.title for s in sources]},
    )
    return sources


def _blocked_response(session_id: str, guard_result: GuardrailResult, latency_ms: float) -> ChatResponse:
    """Build the response returned when input guardrails intercept a message."""
    logger.warning(
        "chat_request_blocked_by_guardrails",
        extra={"session_id": session_id, "flags": [flag.value for flag in guard_result.flags]},
    )
    return ChatResponse(
        session_id=session_id,
        response=guard_result.override_response,
        disclaimer=MEDICAL_DISCLAIMER,
        sources=[],
        guardrail_flags=guard_result.flags,
        is_emergency=guard_result.is_emergency,
        latency_ms=latency_ms,
    )


def _generate_reply(
    llm_client: BaseLLMClient, session_id: str, user_prompt: str, conversation_history: list[ChatMessage]
) -> tuple[str, str, list[GuardrailFlag]]:
    """Call the LLM and run output guardrails.

    Returns (sanitized_text, provider_name, output_guardrail_flags).
    """
    try:
        generation = llm_client.generate(SYSTEM_PROMPT, user_prompt, conversation_history)
    except Exception as exc:
        logger.error("llm_call_failed", extra={"session_id": session_id, "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="The AI assistant is temporarily unavailable. Please try again shortly.",
        ) from exc

    reply_text = generation.text.strip()
    output_flags = guardrails.check_output(reply_text)
    if output_flags:
        reply_text = guardrails.sanitize_output(reply_text)
    return reply_text, generation.provider, output_flags


@app.get("/health", response_model=HealthResponse, tags=["monitoring"])
def health() -> HealthResponse:
    """Liveness/readiness probe - also reports whether the vector store is up."""
    vectorstore_loaded = False
    if settings.rag_enabled:
        try:
            vectorstore_loaded = rag.get_vector_store().is_loaded
        except Exception as exc:
            logger.error("health_check_vectorstore_probe_failed", extra={"error": str(exc)})
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
        llm_provider=settings.llm_provider,
        rag_enabled=settings.rag_enabled,
        vectorstore_loaded=vectorstore_loaded,
    )


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest, memory: MemoryStoreDep, llm_client: LLMClientDep) -> ChatResponse:
    """Handle one conversational turn - see module docstring for the pipeline stages."""
    session_id = request.session_id or new_session_id()
    logger.info("chat_request_received", extra={"session_id": session_id, "message_len": len(request.message)})

    with stopwatch() as elapsed_ms:
        guard_result = guardrails.check_input(request.message)

        if guard_result.blocked and guard_result.override_response:
            memory.add_message(session_id, Role.USER, request.message)
            memory.add_message(session_id, Role.ASSISTANT, guard_result.override_response)
            return _blocked_response(session_id, guard_result, elapsed_ms())

        sources = _retrieve_sources(session_id, request.message)
        conversation_history = memory.get_history(session_id)
        user_prompt = build_user_turn(request.message, sources)

        reply_text, provider_used, output_flags = _generate_reply(
            llm_client, session_id, user_prompt, conversation_history
        )

        memory.add_message(session_id, Role.USER, request.message)
        memory.add_message(session_id, Role.ASSISTANT, reply_text)
        latency_ms = elapsed_ms()

    logger.info(
        "chat_request_completed",
        extra={"session_id": session_id, "latency_ms": round(latency_ms, 1), "provider": provider_used},
    )
    return ChatResponse(
        session_id=session_id,
        response=reply_text,
        disclaimer=MEDICAL_DISCLAIMER,
        sources=sources,
        guardrail_flags=guard_result.flags + output_flags,
        is_emergency=False,
        latency_ms=latency_ms,
    )


@app.post("/clear", response_model=ClearResponse, tags=["chat"])
def clear(request: ClearRequest, memory: MemoryStoreDep) -> ClearResponse:
    """Delete a session's stored conversation history."""
    cleared = memory.clear(request.session_id)
    logger.info("session_cleared", extra={"session_id": request.session_id, "existed": cleared})
    return ClearResponse(session_id=request.session_id, cleared=cleared)


@app.get("/history", response_model=HistoryResponse, tags=["chat"])
def history(session_id: str, memory: MemoryStoreDep) -> HistoryResponse:
    """Return the stored turns for a session (empty list if unknown)."""
    return HistoryResponse(session_id=session_id, messages=memory.get_history(session_id))
