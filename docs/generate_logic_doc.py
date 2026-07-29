"""
Generates docs/Aarogya_Logic_Documentation.pdf — a professional writeup of
how the system processes queries, builds prompts, runs RAG, maintains
memory, and enforces safety guardrails.
"""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem,
    Table, TableStyle, PageBreak, HRFlowable,
)

OUT = Path(__file__).parent / "Aarogya_Logic_Documentation.pdf"

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "TitleCustom", parent=styles["Title"], fontSize=24, textColor=colors.HexColor("#1a3a6b"),
    spaceAfter=6,
)
subtitle_style = ParagraphStyle(
    "SubtitleCustom", parent=styles["Normal"], fontSize=12, textColor=colors.HexColor("#5b6579"),
    spaceAfter=20,
)
h1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#1a3a6b"),
    spaceBefore=18, spaceAfter=8,
)
h2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontSize=12.5, textColor=colors.HexColor("#2b5bd7"),
    spaceBefore=10, spaceAfter=6,
)
body = ParagraphStyle(
    "BodyCustom", parent=styles["BodyText"], fontSize=10.2, leading=15, spaceAfter=8,
)
bullet_style = ParagraphStyle(
    "BulletCustom", parent=styles["BodyText"], fontSize=10.2, leading=14.5,
)
caption = ParagraphStyle(
    "Caption", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#8a93a8"),
)

doc = SimpleDocTemplate(
    str(OUT), pagesize=LETTER,
    leftMargin=0.85 * inch, rightMargin=0.85 * inch,
    topMargin=0.9 * inch, bottomMargin=0.8 * inch,
    title="Aarogya Healthcare Chatbot — Logic Documentation",
)

story = []

story.append(Paragraph("Aarogya Healthcare Chatbot", title_style))
story.append(Paragraph("System Logic &amp; Technical Documentation", subtitle_style))
story.append(HRFlowable(width="100%", color=colors.HexColor("#e4e9f2"), thickness=1))
story.append(Spacer(1, 14))


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(i, bullet_style), leftIndent=6) for i in items],
        bulletType="bullet", start="•", leftIndent=16, spaceBefore=2, spaceAfter=8,
    )


# 1. Overview -----------------------------------------------------------
story.append(Paragraph("1. Overview", h1))
story.append(Paragraph(
    "Aarogya is a Retrieval-Augmented Generation (RAG) healthcare information "
    "chatbot. It answers general questions on symptoms, diseases, nutrition, "
    "preventive care, healthy lifestyle, and first aid, while strictly avoiding "
    "diagnosis, prescriptions, and dosage recommendations. This document explains "
    "how a single user message flows through the system end to end.",
    body,
))

# 2. Query processing -----------------------------------------------------
story.append(Paragraph("2. How Queries Are Processed", h1))
story.append(Paragraph(
    "Every call to <b>POST /chat</b> is handled by a single orchestration function "
    "in <font face='Courier'>app/api.py</font> that runs the following pipeline in order:",
    body,
))
story.append(bullets([
    "<b>Session resolution</b> — an existing <font face='Courier'>session_id</font> is reused, "
    "or a new UUID is generated.",
    "<b>Input guardrails</b> — the raw message is scanned for emergencies, prompt injection/leak "
    "attempts, and risky request types (see Section 5). If the message is blocked, a deterministic "
    "response is returned immediately and the LLM is never called.",
    "<b>RAG retrieval</b> — if not blocked, the message is embedded and the top-k most similar "
    "knowledge-base chunks are retrieved (see Section 4).",
    "<b>Prompt assembly</b> — the system prompt, retrieved context, and question are combined into "
    "a single user turn (see Section 3).",
    "<b>LLM call</b> — the configured provider (OpenAI or Gemini) generates a response, with retry "
    "and fallback-model logic.",
    "<b>Output guardrails</b> — the generated text is swept for residual diagnosis/dosage language "
    "and sanitized if needed.",
    "<b>Memory update</b> — both turns are appended to the session's conversation history.",
    "<b>Response</b> — a structured JSON object is returned: response text, standard medical "
    "disclaimer, source citations, guardrail flags, emergency flag, and latency.",
]))

# 3. Prompt engineering -----------------------------------------------------
story.append(Paragraph("3. How Prompts Are Built", h1))
story.append(Paragraph(
    "Prompt construction lives entirely in <font face='Courier'>app/prompts.py</font>, separated "
    "from orchestration logic so it can be reviewed and unit-tested independently.",
    body,
))
story.append(Paragraph("System prompt", h2))
story.append(Paragraph(
    "A fixed system prompt establishes the assistant's persona (\"Aarogya\"), tone "
    "(friendly, empathetic, concise), and — critically — a list of things it must "
    "never do: diagnose, prescribe, recommend dosages, interpret personal lab "
    "results, or tell a user to change a prescribed treatment. It also instructs "
    "the model to stay in character and decline attempts to override these rules.",
    body,
))
story.append(Paragraph("User turn", h2))
story.append(Paragraph(
    "Each user turn is built by <font face='Courier'>build_user_turn()</font>, which wraps the "
    "retrieved context chunks (numbered, with source labels) together with the "
    "user's question and a short instruction to ground the answer in that context "
    "when relevant, without fabricating information the context doesn't support.",
    body,
))
story.append(Paragraph("Conversation history", h2))
story.append(Paragraph(
    "The last <font face='Courier'>MAX_MEMORY_TURNS</font> exchanges for the session are passed to the "
    "LLM client alongside the system and user prompts, so follow-up questions "
    "(\"can I exercise?\" after \"I have a fever\") are answered with prior context "
    "in mind.",
    body,
))

# 4. RAG -----------------------------------------------------
story.append(Paragraph("4. How Retrieval-Augmented Generation Works", h1))
story.append(Paragraph("Indexing (offline / on startup)", h2))
story.append(bullets([
    "Documents in <font face='Courier'>knowledge_base/docs/</font> (WHO/CDC/NIH/MedlinePlus-style "
    "reference material) are read and split into ~500-word overlapping chunks "
    "(<font face='Courier'>app/rag.py: chunk_text()</font>).",
    "Each chunk is embedded with the <font face='Courier'>all-MiniLM-L6-v2</font> Sentence-Transformers "
    "model (384-dim, normalized for cosine similarity).",
    "Embeddings are stored in a FAISS <font face='Courier'>IndexFlatIP</font> index, persisted to "
    "<font face='Courier'>vectorstore/index.faiss</font> alongside a JSON metadata sidecar "
    "(<font face='Courier'>vectorstore/metadata.json</font>) mapping vector positions back to chunk "
    "text, title, and source.",
])
)
story.append(Paragraph("Retrieval (per query)", h2))
story.append(bullets([
    "The user's question is embedded with the same model.",
    "FAISS returns the top-<font face='Courier'>k</font> (default 4) most similar chunks by inner-product "
    "score.",
    "Each result becomes a <font face='Courier'>SourceDocument</font> (title, source, snippet, score) that is "
    "both injected into the prompt as grounding context and returned to the "
    "client as a citation.",
])
)
story.append(Paragraph(
    "If no documents are found relevant, or RAG is disabled "
    "(<font face='Courier'>RAG_ENABLED=false</font>), the LLM answers from general knowledge under "
    "the same safety constraints — the system degrades gracefully rather than "
    "failing the request.",
    body,
))

# 5. Guardrails -----------------------------------------------------
story.append(PageBreak())
story.append(Paragraph("5. How Guardrails Work", h1))
story.append(Paragraph(
    "Guardrails are implemented as fast, deterministic, unit-testable regex/keyword "
    "rules in <font face='Courier'>app/guardrails.py</font> — deliberately not a second LLM call, so "
    "they have no dependency on an external API and cannot themselves be prompt-"
    "injected.",
    body,
))
story.append(Paragraph("Input-side checks (before the LLM is called)", h2))

# Table cells must be Paragraph objects, not raw strings - a plain string is
# drawn as a single unwrapped line and silently overflows past its column
# width instead of wrapping, which clips or overlaps neighboring cells.
table_header_style = ParagraphStyle(
    "TableHeader", parent=styles["BodyText"], fontSize=8.6, leading=11,
    textColor=colors.white, fontName="Helvetica-Bold",
)
table_cell_style = ParagraphStyle(
    "TableCell", parent=styles["BodyText"], fontSize=8.6, leading=11.5,
    textColor=colors.HexColor("#16202e"), spaceAfter=0, spaceBefore=0,
)

table_rows = [
    ["Category", "Examples matched", "Action"],
    [
        "Medical emergency",
        "Chest pain, difficulty breathing, stroke symptoms, severe bleeding, "
        "loss of consciousness, anaphylaxis",
        "Blocked — deterministic emergency response with local emergency numbers",
    ],
    [
        "Mental health crisis",
        "Suicidal ideation, self-harm language",
        "Blocked — emergency response plus crisis helpline numbers",
    ],
    [
        "Prompt injection",
        "\u201cIgnore previous instructions\u201d, \u201cact as...\u201d, \u201coverride your rules\u201d",
        "Blocked — polite refusal, conversation continues",
    ],
    [
        "Prompt leak attempt",
        "\u201cShow me your system prompt\u201d",
        "Blocked — polite refusal",
    ],
    [
        "Illegal drug advice",
        "Synthesis instructions, \u201cget high on...\u201d",
        "Blocked — redirect to support resources",
    ],
    [
        "Diagnosis request",
        "\u201cDo I have...\u201d, \u201cwhat's wrong with me\u201d",
        "Flagged only — LLM redirects per system prompt",
    ],
    [
        "Dosage / prescription request",
        "\u201cHow many mg\u201d, \u201cprescribe me...\u201d",
        "Flagged only — LLM redirects per system prompt",
    ],
]

data = [
    [Paragraph(cell, table_header_style if row_index == 0 else table_cell_style) for cell in row]
    for row_index, row in enumerate(table_rows)
]
tbl = Table(data, colWidths=[1.55 * inch, 2.55 * inch, 2.15 * inch], repeatRows=1)
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a6b")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e4e9f2")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fb")]),
    ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
story.append(tbl)
story.append(Spacer(1, 10))

story.append(Paragraph(
    "\"Blocked\" categories skip the LLM entirely and return a fixed, reviewed "
    "response — this guarantees emergency guidance is always correct and instant, "
    "and can never be altered by a jailbreak of the LLM itself. \"Flagged\" "
    "categories still reach the LLM, which is instructed by the system prompt to "
    "redirect rather than comply, giving a more natural, context-aware response "
    "for borderline cases.",
    body,
))

story.append(Paragraph("Output-side checks (after the LLM responds)", h2))
story.append(Paragraph(
    "As defense in depth, the LLM's own generated text is swept for residual "
    "diagnosis language (\"you have a...\") or dosage language (\"take 500 mg...\"). "
    "If found, the offending phrase is replaced with a safe redirect "
    "(\"take a dose recommended by your doctor or pharmacist\") and a note is "
    "appended informing the user that a specific figure was removed for safety.",
    body,
))

# 6. Memory -----------------------------------------------------
story.append(Paragraph("6. How Memory Works", h1))
story.append(Paragraph(
    "Conversation memory is a thread-safe, per-session, in-process store "
    "(<font face='Courier'>app/memory.py: MemoryStore</font>) keyed by "
    "<font face='Courier'>session_id</font>. Each session keeps a sliding window of the most "
    "recent <font face='Courier'>MAX_MEMORY_TURNS</font> exchanges (default 10 user+assistant pairs); "
    "older turns are trimmed automatically to bound memory and prompt size. "
    "The store is abstracted behind a small interface so a persistent backend "
    "(Redis, Postgres) can be substituted later without touching callers.",
    body,
))

# 7. Safety measures -----------------------------------------------------
story.append(Paragraph("7. Safety Measures Summary", h1))
story.append(bullets([
    "Hard-coded system-prompt boundaries against diagnosis, prescriptions, and dosages.",
    "Deterministic, LLM-independent emergency interception with region-appropriate "
    "helpline numbers.",
    "Defense-in-depth output sanitization in case the LLM slips despite instructions.",
    "Mandatory medical disclaimer attached to every response.",
    "Prompt-injection and prompt-leak detection that short-circuits the LLM call.",
    "Structured logging of every request, its guardrail flags, and latency for "
    "auditability.",
]))

# 8. Challenges -----------------------------------------------------
story.append(Paragraph("8. Challenges", h1))
story.append(bullets([
    "<b>Balancing helpfulness and safety</b> — over-blocking makes the assistant "
    "useless for legitimate education (e.g. \"what causes a fever\" vs. \"do I have "
    "a fever-causing disease\"); the current rules flag rather than block borderline "
    "diagnosis/dosage phrasing so the LLM can still give a safe, redirecting answer.",
    "<b>Regex coverage vs. natural language variety</b> — users phrase emergencies "
    "and risky requests in many ways; the pattern banks are deliberately broad "
    "(multiple synonyms per category) but can't catch every paraphrase, which is "
    "why output-side sanitization exists as a second layer.",
    "<b>Grounding without over-constraining</b> — RAG context should inform, not "
    "straitjacket, answers to questions the knowledge base doesn't cover; the "
    "prompt explicitly allows general medical knowledge when context is irrelevant, "
    "while still forbidding fabrication.",
    "<b>Provider abstraction</b> — OpenAI and Gemini have different chat-history and "
    "system-prompt conventions; a common <font face='Courier'>BaseLLMClient</font> interface hides "
    "this so the rest of the app is provider-agnostic.",
]))

# 9. Future improvements -----------------------------------------------------
story.append(Paragraph("9. Future Improvements", h1))
story.append(bullets([
    "LLM-based secondary guardrail classifier for higher recall on paraphrased risk.",
    "Persistent (Redis/Postgres) memory so sessions survive restarts and scale "
    "across workers.",
    "Streaming responses (SSE/WebSocket) for a more responsive chat feel.",
    "Multilingual input/output and voice input/speech output.",
    "Expanded, properly licensed knowledge base ingested directly from WHO/CDC/"
    "NIH/MedlinePlus feeds.",
    "Response caching for frequently asked questions to reduce latency and cost.",
]))

story.append(Spacer(1, 20))
story.append(HRFlowable(width="100%", color=colors.HexColor("#e4e9f2"), thickness=1))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "Aarogya Healthcare Chatbot — Logic Documentation · Educational use only, not a "
    "substitute for professional medical advice.",
    caption,
))

doc.build(story)
print(f"PDF written to {OUT}")
