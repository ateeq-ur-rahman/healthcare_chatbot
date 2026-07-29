# Aarogya — Healthcare AI Chatbot

A chatbot that answers general health questions — symptoms, nutrition, first aid,
preventive care — using RAG for grounding and a rule-based guardrail layer for
safety. Built as a reference implementation for a "healthcare chatbot" assignment,
but structured the way I'd actually want to maintain it: swappable LLM provider,
regex-based safety checks that don't depend on the model behaving itself, and a
FastAPI backend that doesn't care what frontend is talking to it.

**This is not a medical device.** It doesn't diagnose, doesn't prescribe, and
every response carries a disclaimer. If a message looks like an emergency, it
gets intercepted before the LLM ever sees it and gets a fixed, reviewed response
with emergency numbers instead.

## Why it's built this way

A few decisions that might look unusual at first glance:

- **Guardrails are regex, not a second LLM call.** An LLM classifier can itself
  be talked out of doing its job with a cleverly worded message. Regex can't be
  jailbroken — it either matches or it doesn't. The tradeoff is recall on
  paraphrased requests, which is why there's also an output-side sweep as a
  second layer (see `app/guardrails.py`).
- **Emergency detection short-circuits everything else.** If a message mentions
  chest pain or suicidal ideation, steps 2-6 of the pipeline never run. The
  emergency response is hardcoded and reviewed, not generated, so it can never
  come out wrong or get talked around.
- **The LLM provider is swappable via config, not code.** `LLM_PROVIDER=openai`
  or `gemini` and nothing else changes. Useful when you want to compare cost/
  latency/quality between providers without touching the API layer.
- **No LLM key configured? The app still runs.** There's an offline demo client
  that returns a clearly-labeled placeholder response, so the guardrails/RAG/
  memory pipeline is fully testable (and CI-friendly) without a paid API key.

## Architecture

```
Streamlit frontend  --HTTP/JSON-->  FastAPI backend
                                        |
                                        |-- 1. input guardrails (emergency? blocked category?)
                                        |-- 2. RAG retrieval (FAISS, top-4 chunks)
                                        |-- 3. prompt assembly (system + context + history)
                                        |-- 4. LLM call (OpenAI or Gemini, retried)
                                        |-- 5. output guardrails (sanitize if needed)
                                        |-- 6. memory update (per-session, in-process)
                                        `-- 7. structured response (text + disclaimer + sources)
```

Frontend and backend are fully decoupled — the Streamlit app just calls the
HTTP API, so you could swap in a different UI without touching `app/` at all.

## Features

- Chat interface (Streamlit) with dark/light mode, sidebar history, suggested
  questions, source citations, and thumbs up/down feedback buttons
- FastAPI backend with a clean pipeline: guardrails → RAG → prompt → LLM →
  guardrails → memory
- RAG over a small knowledge base (Sentence-Transformers + FAISS), top-4
  retrieval with citations returned in the API response
- Provider-agnostic LLM client (OpenAI GPT-5/4.1 fallback, or Gemini 2.5
  Flash) via a Strategy-pattern abstraction
- Guardrails for: medical emergencies, mental-health crisis, diagnosis
  requests, dosage/prescription requests, illegal-drug requests, prompt
  injection, and prompt-leak attempts
- Per-session conversation memory (sliding window, thread-safe)
- Structured JSON logging (requests, latency, guardrail flags, errors)
- 42 unit/integration tests, no external services required to run them
- Docker + docker-compose for both services

## Installation

Requires Python 3.11+ and pip.

```bash
git clone <your-repo-url>
cd healthcare-chatbot

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# edit .env: set LLM_PROVIDER and the matching API key
```

Build the vector store once (it also auto-builds on first backend startup
if missing, this just makes the first request faster):

```bash
python -m app.rag
```

## Running locally

Backend:
```bash
uvicorn app.main:app --reload --port 8000
```

Frontend, in a second terminal:
```bash
export BACKEND_API_URL=http://localhost:8000   # Windows: set BACKEND_API_URL=...
streamlit run frontend/streamlit_app.py
```

- UI: http://localhost:8501
- API docs (Swagger): http://localhost:8000/docs

Or with Docker:
```bash
cp .env.example .env   # fill in your key first
docker compose up --build
```

## Environment variables

Everything is read through `app/config.py` (Pydantic Settings) — see
`.env.example` for the full list with defaults. The ones you actually need to
touch:

| Variable | What it does | Default |
|---|---|---|
| `LLM_PROVIDER` | `openai` or `gemini` | `openai` |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | Provider credential | — |
| `OPENAI_MODEL` / `OPENAI_FALLBACK_MODEL` | Primary + fallback model | `gpt-5` / `gpt-4.1` |
| `RAG_ENABLED` | Turn retrieval on/off | `true` |
| `RAG_TOP_K` | Chunks retrieved per query | `4` |
| `MAX_MEMORY_TURNS` | Conversation turns kept per session | `10` |
| `BACKEND_API_URL` | Used by the Streamlit app to find the backend | `http://localhost:8000` |

No API key configured? The backend falls back to an offline demo client
instead of failing outright — useful for local development and CI.

## Folder structure

```
healthcare-chatbot/
├── app/
│   ├── main.py          # uvicorn entrypoint
│   ├── api.py             # FastAPI routes + request orchestration
│   ├── llm.py               # OpenAI / Gemini abstraction (Strategy pattern)
│   ├── prompts.py            # system prompt + prompt assembly
│   ├── rag.py                  # chunking, FAISS index, retrieval
│   ├── embeddings.py            # Sentence-Transformers wrapper
│   ├── memory.py                 # per-session conversation memory
│   ├── guardrails.py              # input/output safety checks
│   ├── models.py                   # Pydantic request/response schemas
│   ├── config.py                    # env-driven settings
│   └── utils.py                      # logging, retry, stopwatch helpers
├── frontend/
│   ├── streamlit_app.py    # chat UI
│   └── Dockerfile
├── knowledge_base/docs/     # reference material chunked into the vector store
├── vectorstore/               # persisted FAISS index (generated, gitignored)
├── tests/                       # pytest suite
├── docs/                          # architecture deck + logic write-up
├── Dockerfile                       # backend image
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## API endpoints

Full interactive docs at `/docs` once the backend is running. Summary:

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | Send a message, get a response + disclaimer + sources |
| `GET` | `/health` | Liveness check, reports LLM provider and vector-store status |
| `POST` | `/clear` | Clear a session's stored history |
| `GET` | `/history` | Fetch a session's stored history |

`POST /chat` request/response shape:

```json
// request
{ "session_id": "optional-existing-id", "message": "What are some tips for a balanced diet?" }

// response
{
  "session_id": "uuid",
  "response": "...",
  "disclaimer": "This information is educational only...",
  "sources": [{ "title": "...", "source": "NIH / MedlinePlus", "snippet": "...", "score": 0.83 }],
  "guardrail_flags": [],
  "is_emergency": false,
  "latency_ms": 812.4
}
```

## Testing

```bash
pytest
```

Tests run with `RAG_ENABLED=false` and no LLM key (see `tests/conftest.py`),
so the whole pipeline — guardrails, RAG (skipped), LLM abstraction (offline
demo client), memory, API — runs without needing an API key or the heavier
optional dependencies (`torch`, `faiss`) installed. Set a real key and
`RAG_ENABLED=true` if you want to exercise the live path.

## Future improvements

Things I'd tackle next, roughly in priority order:

- **Persistent memory.** Right now `MemoryStore` is in-process, so history is
  lost on restart and doesn't work across multiple workers. Swapping in Redis
  is the obvious next step — `MemoryStore`'s interface is already small enough
  that it shouldn't touch any callers.
- **Cache the LLM client per process** instead of constructing a new
  OpenAI/Gemini client object on every request — currently it's re-initialized
  each call via the `Depends(get_llm_client)` wiring, which works but is
  wasteful.
- **LLM-based secondary guardrail.** The regex layer catches the phrasing I
  thought to write patterns for, but a paraphrased request can slip through.
  A cheap classifier call as a second opinion would improve recall without
  giving up the deterministic-blocking property for the cases regex already
  catches.
- **Streaming responses** over SSE/WebSocket instead of waiting for the full
  generation.
- **Real knowledge base.** The docs in `knowledge_base/docs/` are illustrative
  summaries I wrote, not actual WHO/CDC/NIH source material — swap in properly
  licensed content before this goes anywhere near production.
- Multilingual support (the `language` field is already on `ChatRequest`,
  just not wired up to anything yet), voice input/output, PDF chat export,
  response caching for repeated questions.

## Disclaimer

Built to strict safety constraints (no diagnosis, no prescriptions, no
dosages, mandatory disclaimers, deterministic emergency handling) but this
is a portfolio/assignment project, not a certified medical device. Don't use
it as a sole source of guidance for real medical decisions.
