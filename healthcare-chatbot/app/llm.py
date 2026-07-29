"""Provider-agnostic LLM client.

The rest of the app talks to `get_llm_client()` and calls
`.generate(system_prompt, user_prompt, history)` - it never knows or
cares whether the underlying provider is OpenAI or Gemini. Switching
providers is a one-line config change (`LLM_PROVIDER=openai|gemini`).

Design: an abstract base class (`BaseLLMClient`) plus one concrete
implementation per provider plus a factory function - the Strategy
pattern. Each provider's SDK quirks (message format, history shape,
model instantiation) stay isolated inside its own class.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

from app.config import settings
from app.models import ChatMessage, Role
from app.utils import get_logger, stopwatch, with_retries

logger = get_logger(__name__)


class LLMError(RuntimeError):
    """Raised when an LLM provider can't be initialized or a call fails after retries."""


@dataclass
class LLMResult:
    """A completed generation, along with which provider/model actually served it."""

    text: str
    provider: str
    model: str
    latency_ms: float


class BaseLLMClient(abc.ABC):
    """Strategy interface every LLM provider client implements."""

    provider_name: str = "base"

    @abc.abstractmethod
    def _call(self, system_prompt: str, user_prompt: str, history: list[ChatMessage]) -> str:
        """Provider-specific call. Raise on failure - `generate()` handles retries."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[ChatMessage] | None = None,
    ) -> LLMResult:
        """Generate a response, retrying transient failures with backoff."""
        retrying_call = with_retries(
            max_attempts=settings.llm_max_retries,
            base_delay_seconds=0.5,
        )(self._call)

        with stopwatch() as elapsed_ms:
            text = retrying_call(system_prompt, user_prompt, history or [])

        return LLMResult(
            text=text, provider=self.provider_name, model=self.model_name, latency_ms=elapsed_ms()
        )


def _history_to_openai_messages(history: list[ChatMessage]) -> list[dict[str, str]]:
    return [
        {"role": "assistant" if msg.role == Role.ASSISTANT else "user", "content": msg.content}
        for msg in history
    ]


def _history_to_gemini_turns(history: list[ChatMessage]) -> list[dict]:
    return [
        {"role": "model" if msg.role == Role.ASSISTANT else "user", "parts": [msg.content]}
        for msg in history
    ]


class OpenAIClient(BaseLLMClient):
    """Chat Completions client, with automatic fallback to a secondary model."""

    provider_name = "openai"

    def __init__(self) -> None:
        try:
            from openai import OpenAI  # optional dependency, imported lazily
        except ImportError as exc:
            raise LLMError(
                "The 'openai' package is required for LLM_PROVIDER=openai. "
                "Install it with `pip install openai`."
            ) from exc

        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is not set.")

        self._client = OpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds)
        self._model = settings.openai_model
        self._fallback_model = settings.openai_fallback_model

    @property
    def model_name(self) -> str:
        return self._model

    def _call(self, system_prompt: str, user_prompt: str, history: list[ChatMessage]) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            *_history_to_openai_messages(history),
            {"role": "user", "content": user_prompt},
        ]
        try:
            return self._complete(self._model, messages)
        except Exception as exc:
            # Broad catch is deliberate: the OpenAI SDK raises several
            # distinct exception types for rate limits, timeouts, and
            # server errors, and we want the same fallback behavior for
            # all of them rather than enumerating each one.
            logger.warning(
                "openai_primary_model_failed_trying_fallback",
                extra={"model": self._model, "fallback": self._fallback_model, "error": str(exc)},
            )
            reply = self._complete(self._fallback_model, messages)
            self._model = self._fallback_model
            return reply

    def _complete(self, model: str, messages: list[dict[str, str]]) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
        return response.choices[0].message.content or ""


class GeminiClient(BaseLLMClient):
    """Google Generative AI (Gemini) client."""

    provider_name = "gemini"

    def __init__(self) -> None:
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise LLMError(
                "The 'google-generativeai' package is required for LLM_PROVIDER=gemini. "
                "Install it with `pip install google-generativeai`."
            ) from exc

        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set.")

        genai.configure(api_key=settings.gemini_api_key)
        self._genai = genai
        self._model = settings.gemini_model

    @property
    def model_name(self) -> str:
        return self._model

    def _call(self, system_prompt: str, user_prompt: str, history: list[ChatMessage]) -> str:
        model = self._genai.GenerativeModel(model_name=self._model, system_instruction=system_prompt)
        chat = model.start_chat(history=_history_to_gemini_turns(history))
        response = chat.send_message(
            user_prompt,
            generation_config={
                "temperature": settings.llm_temperature,
                "max_output_tokens": settings.llm_max_tokens,
            },
        )
        return response.text or ""


class OfflineDemoClient(BaseLLMClient):
    """Fallback used when no provider API key is configured.

    Lets the rest of the pipeline (guardrails, RAG, memory, API) be
    exercised - in local demos, CI, and tests - without a live network
    call or a paid API key.
    """

    provider_name = "offline-demo"

    @property
    def model_name(self) -> str:
        return "offline-demo"

    def _call(self, system_prompt: str, user_prompt: str, history: list[ChatMessage]) -> str:
        return (
            "[Demo mode — no LLM API key configured] I would normally answer your "
            "health question here using the configured LLM, grounded in the "
            "retrieved reference material. Please set OPENAI_API_KEY or "
            "GEMINI_API_KEY in your .env file to get real answers."
        )


def get_llm_client() -> BaseLLMClient:
    """Return the configured provider's client, falling back to demo mode if unconfigured."""
    try:
        if settings.llm_provider == "openai":
            return OpenAIClient()
        if settings.llm_provider == "gemini":
            return GeminiClient()
    except LLMError as exc:
        logger.warning("llm_client_init_failed_using_offline_demo", extra={"error": str(exc)})
        return OfflineDemoClient()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
