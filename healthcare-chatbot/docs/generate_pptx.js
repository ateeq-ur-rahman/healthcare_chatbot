const path = require("path");
const pptxgen = require("pptxgenjs");

const COLORS = {
  primary: "028090",   // deep teal
  secondary: "00A896", // seafoam
  accent: "02C39A",    // mint
  navy: "1E2761",
  ink: "16202E",
  sub: "5B6579",
  bgLight: "F6F8FB",
  card: "FFFFFF",
  border: "E4E9F2",
  white: "FFFFFF",
  warn: "B85042",
};

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
const PW = 13.333, PH = 7.5;

function baseSlide(bg) {
  const s = pres.addSlide();
  s.background = { color: bg || COLORS.bgLight };
  return s;
}

function footer(s, pageNum, dark) {
  s.addText("AAROGYA — Healthcare AI Chatbot", {
    x: 0.5, y: PH - 0.42, w: 6, h: 0.3, fontSize: 9,
    color: dark ? "9AA4B8" : COLORS.sub, fontFace: "Calibri",
  });
  s.addText(String(pageNum), {
    x: PW - 1.0, y: PH - 0.42, w: 0.5, h: 0.3, fontSize: 9,
    color: dark ? "9AA4B8" : COLORS.sub, align: "right", fontFace: "Calibri",
  });
}

function pill(s, text, x, y, w, opts = {}) {
  s.addShape("roundRect", {
    x, y, w, h: 0.34, rectRadius: 0.17,
    fill: { color: opts.fill || COLORS.primary },
    line: { type: "none" },
  });
  s.addText(text, {
    x, y, w, h: 0.34, align: "center", valign: "middle",
    fontSize: opts.fontSize || 10, color: opts.color || COLORS.white,
    bold: true, fontFace: "Calibri",
  });
}

// ===========================================================================
// SLIDE 1 — Problem Statement
// ===========================================================================
{
  const s = baseSlide(COLORS.navy);

  s.addShape("rect", { x: 0, y: 0, w: PW, h: PH, fill: { color: COLORS.navy }, line: { type: "none" } });
  // Decorative soft circles (motif: layered circles, reused across deck)
  s.addShape("ellipse", { x: 10.6, y: -1.6, w: 5.5, h: 5.5, fill: { color: "0E3A45" }, line: { type: "none" } });
  s.addShape("ellipse", { x: 11.6, y: -0.7, w: 3.6, h: 3.6, fill: { color: "0B4B52" }, line: { type: "none" } });

  s.addText("HEALTHCARE AI CHATBOT — ASSIGNMENT ARCHITECTURE", {
    x: 0.7, y: 0.55, w: 9, h: 0.35, fontSize: 12, color: COLORS.accent,
    bold: true, charSpacing: 1.2, fontFace: "Calibri",
  });
  s.addText("The Problem", {
    x: 0.7, y: 0.95, w: 9, h: 1.0, fontSize: 44, bold: true, color: COLORS.white,
    fontFace: "Cambria",
  });
  s.addText(
    "General health information is scattered, inconsistent, and often written for clinicians — " +
    "not the person searching at 11pm wondering if their symptoms are serious.",
    { x: 0.7, y: 1.85, w: 7.6, h: 0.9, fontSize: 14, color: "CADCFC", fontFace: "Calibri", lineSpacingMultiple: 1.25 }
  );

  const problems = [
    ["Unreliable self-diagnosis", "People turn to generic search results and forums, mixing sound public-health guidance with speculation."],
    ["No safe first stop", "Existing chatbots either over-promise (quasi-diagnosis) or under-deliver (generic disclaimers, no real answer)."],
    ["Risk of harm", "Unqualified medication or dosage advice, or a missed emergency, can cause real harm if a bot gets this wrong."],
  ];

  let cardY = 3.1, cardH = 1.15, gap = 0.28;
  problems.forEach((p, i) => {
    const y = cardY + i * (cardH + gap);
    s.addShape("roundRect", {
      x: 0.7, y, w: 7.6, h: cardH, rectRadius: 0.08,
      fill: { color: "10233F" }, line: { color: "1C3A5C", width: 1 },
    });
    s.addShape("roundRect", {
      x: 0.95, y: y + 0.22, w: 0.5, h: 0.5, rectRadius: 0.08,
      fill: { color: COLORS.accent }, line: { type: "none" },
    });
    s.addText(String(i + 1), {
      x: 0.95, y: y + 0.22, w: 0.5, h: 0.5, align: "center", valign: "middle",
      fontSize: 16, bold: true, color: COLORS.navy, fontFace: "Calibri",
    });
    s.addText(p[0], {
      x: 1.65, y: y + 0.12, w: 6.4, h: 0.35, fontSize: 14.5, bold: true, color: COLORS.white, fontFace: "Calibri",
    });
    s.addText(p[1], {
      x: 1.65, y: y + 0.46, w: 6.4, h: 0.6, fontSize: 10.5, color: "AEB9CF", fontFace: "Calibri", lineSpacingMultiple: 1.15,
    });
  });

  // Right column: goal callout card
  s.addShape("roundRect", {
    x: 8.7, y: 1.85, w: 3.95, h: 4.68, rectRadius: 0.1,
    fill: { color: "072430" }, line: { color: COLORS.accent, width: 1.25 },
  });
  s.addText("OUR GOAL", {
    x: 9.0, y: 2.15, w: 3.4, h: 0.3, fontSize: 11, bold: true, color: COLORS.accent,
    charSpacing: 1.2, fontFace: "Calibri",
  });
  s.addText(
    "Build a chatbot that answers everyday health questions clearly and empathetically — " +
    "while being structurally incapable of diagnosing or prescribing.",
    { x: 9.0, y: 2.5, w: 3.4, h: 1.3, fontSize: 13.5, color: COLORS.white, fontFace: "Cambria", italic: true, lineSpacingMultiple: 1.3 }
  );

  const goals = ["Grounded, cited answers (RAG)", "Deterministic emergency handling", "Always-on medical disclaimer", "Provider-agnostic LLM layer"];
  let gy = 4.1;
  goals.forEach((g) => {
    s.addShape("ellipse", { x: 9.0, y: gy + 0.06, w: 0.12, h: 0.12, fill: { color: COLORS.secondary }, line: { type: "none" } });
    s.addText(g, { x: 9.28, y: gy - 0.08, w: 3.15, h: 0.4, fontSize: 11.5, color: "DCE6F5", fontFace: "Calibri" });
    gy += 0.5;
  });

  footer(s, 1, true);
}

// ===========================================================================
// SLIDE 2 — Architecture Diagram
// ===========================================================================
{
  const s = baseSlide(COLORS.bgLight);
  s.addText("System Architecture", { x: 0.6, y: 0.4, w: 8, h: 0.5, fontSize: 28, bold: true, color: COLORS.ink, fontFace: "Cambria" });
  s.addText("Three-tier design: Streamlit frontend, FastAPI orchestration backend, external LLM providers", {
    x: 0.6, y: 0.9, w: 10.5, h: 0.35, fontSize: 12.5, color: COLORS.sub, fontFace: "Calibri",
  });

  // Frontend tier
  s.addShape("roundRect", { x: 0.6, y: 1.55, w: 12.1, h: 0.85, rectRadius: 0.08, fill: { color: COLORS.navy }, line: { type: "none" } });
  s.addText("STREAMLIT FRONTEND", { x: 0.9, y: 1.65, w: 3.5, h: 0.3, fontSize: 11, bold: true, color: COLORS.accent, charSpacing: 1, fontFace: "Calibri" });
  s.addText("Chat UI  ·  Dark/Light mode  ·  Sidebar history  ·  Source chips  ·  Feedback buttons", {
    x: 0.9, y: 1.95, w: 11.5, h: 0.35, fontSize: 12, color: COLORS.white, fontFace: "Calibri",
  });

  // Arrow down
  s.addShape("downArrow", { x: 6.25, y: 2.42, w: 0.35, h: 0.28, fill: { color: COLORS.secondary }, line: { type: "none" } });
  s.addText("HTTP / JSON", { x: 6.7, y: 2.4, w: 1.6, h: 0.3, fontSize: 9, italic: true, color: COLORS.sub, fontFace: "Calibri" });

  // Backend tier container
  s.addShape("roundRect", { x: 0.6, y: 2.78, w: 12.1, h: 3.55, rectRadius: 0.08, fill: { color: COLORS.card }, line: { color: COLORS.border, width: 1 } });
  s.addText("FASTAPI BACKEND  (app/)", { x: 0.9, y: 2.92, w: 5, h: 0.3, fontSize: 11, bold: true, color: COLORS.primary, charSpacing: 1, fontFace: "Calibri" });

  const modules = [
    ["api.py", "Endpoint orchestration"],
    ["guardrails.py", "Safety rules & emergencies"],
    ["rag.py / embeddings.py", "FAISS retrieval"],
    ["prompts.py", "Prompt engineering"],
    ["llm.py", "OpenAI / Gemini abstraction"],
    ["memory.py", "Per-session history"],
    ["models.py", "Pydantic schemas"],
    ["config.py / utils.py", "Settings & logging"],
  ];
  const cols = 4, rows = 2, mx = 0.9, my = 3.35, mw = 2.85, mh = 1.05, gx = 0.15, gy = 0.15;
  modules.forEach((m, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x = mx + col * (mw + gx);
    const y = my + row * (mh + gy);
    s.addShape("roundRect", { x, y, w: mw, h: mh, rectRadius: 0.07, fill: { color: COLORS.bgLight }, line: { color: COLORS.border, width: 1 } });
    s.addText(m[0], { x: x + 0.15, y: y + 0.12, w: mw - 0.3, h: 0.3, fontSize: 11.5, bold: true, color: COLORS.navy, fontFace: "Courier New" });
    s.addText(m[1], { x: x + 0.15, y: y + 0.45, w: mw - 0.3, h: 0.5, fontSize: 9.7, color: COLORS.sub, fontFace: "Calibri", lineSpacingMultiple: 1.1 });
  });

  // Bottom row: external services
  const ext = [
    ["OpenAI GPT-5 / 4.1", COLORS.secondary],
    ["Gemini 2.5 Flash", COLORS.accent],
    ["FAISS Vector Store", COLORS.primary],
  ];
  let ex = 0.9, ey = 6.55, ew = 2.6, eh = 0.55;
  ext.forEach((e, i) => {
    const x = 0.9 + i * (ew + 0.3);
    s.addShape("roundRect", { x, y: ey, w: ew, h: eh, rectRadius: 0.27, fill: { color: e[1] }, line: { type: "none" } });
    s.addText(e[0], { x, y: ey, w: ew, h: eh, align: "center", valign: "middle", fontSize: 10.5, bold: true, color: COLORS.white, fontFace: "Calibri" });
  });
  s.addText("← connects to", { x: 9.5, y: ey + 0.15, w: 1.9, h: 0.3, fontSize: 9.5, italic: true, color: COLORS.sub, fontFace: "Calibri" });

  footer(s, 2, false);
}

// ===========================================================================
// SLIDE 3 — Workflow
// ===========================================================================
{
  const s = baseSlide(COLORS.bgLight);
  s.addText("Request Workflow", { x: 0.6, y: 0.4, w: 8, h: 0.5, fontSize: 28, bold: true, color: COLORS.ink, fontFace: "Cambria" });
  s.addText("What happens between a user's message and Aarogya's reply", {
    x: 0.6, y: 0.9, w: 10.5, h: 0.35, fontSize: 12.5, color: COLORS.sub, fontFace: "Calibri",
  });

  const steps = [
    ["1", "Input Guardrails", "Scan for emergencies, prompt injection, risky requests", COLORS.warn],
    ["2", "RAG Retrieval", "Embed query, fetch top-4 chunks from FAISS", COLORS.primary],
    ["3", "Prompt Assembly", "System prompt + context + conversation history", COLORS.primary],
    ["4", "LLM Generation", "OpenAI or Gemini, with retry & fallback model", COLORS.secondary],
    ["5", "Output Guardrails", "Sweep for residual diagnosis/dosage language", COLORS.warn],
    ["6", "Memory + Response", "Save turn, return answer + disclaimer + sources", COLORS.accent],
  ];

  const startX = 0.65, y = 2.15, boxW = 1.85, boxH = 1.9, gap = 0.17;
  steps.forEach((st, i) => {
    const x = startX + i * (boxW + gap);
    s.addShape("roundRect", { x, y, w: boxW, h: boxH, rectRadius: 0.1, fill: { color: COLORS.card }, line: { color: COLORS.border, width: 1 } });
    s.addShape("ellipse", { x: x + boxW / 2 - 0.28, y: y + 0.2, w: 0.56, h: 0.56, fill: { color: st[3] }, line: { type: "none" } });
    s.addText(st[0], { x: x + boxW / 2 - 0.28, y: y + 0.2, w: 0.56, h: 0.56, align: "center", valign: "middle", fontSize: 18, bold: true, color: COLORS.white, fontFace: "Calibri" });
    s.addText(st[1], { x: x + 0.1, y: y + 0.88, w: boxW - 0.2, h: 0.45, align: "center", fontSize: 11.5, bold: true, color: COLORS.ink, fontFace: "Calibri" });
    s.addText(st[2], { x: x + 0.1, y: y + 1.3, w: boxW - 0.2, h: 0.55, align: "center", fontSize: 8.7, color: COLORS.sub, fontFace: "Calibri", lineSpacingMultiple: 1.1 });
    if (i < steps.length - 1) {
      s.addShape("rightArrow", { x: x + boxW + 0.02, y: y + boxH / 2 - 0.09, w: 0.15, h: 0.18, fill: { color: COLORS.sub }, line: { type: "none" } });
    }
  });

  // Emergency short-circuit callout
  s.addShape("roundRect", { x: 0.65, y: 4.4, w: 12.05, h: 1.15, rectRadius: 0.08, fill: { color: "FDECEC" }, line: { color: "F3B8B8", width: 1 } });
  s.addText("⚠", { x: 0.9, y: 4.62, w: 0.5, h: 0.6, fontSize: 22, color: COLORS.warn, fontFace: "Calibri" });
  s.addText(
    "Emergency short-circuit: if Step 1 detects chest pain, stroke symptoms, severe bleeding, " +
    "loss of consciousness, or suicidal ideation, steps 2–5 are skipped entirely — the user " +
    "immediately receives a fixed, reviewed emergency response with local emergency and crisis " +
    "helpline numbers.",
    { x: 1.5, y: 4.55, w: 10.9, h: 0.9, fontSize: 11.5, color: "7A2A2A", fontFace: "Calibri", lineSpacingMultiple: 1.25 }
  );

  s.addText("Typical end-to-end latency: 0.5s – 2.5s depending on LLM provider and retrieval load.", {
    x: 0.65, y: 5.85, w: 8, h: 0.35, fontSize: 10.5, italic: true, color: COLORS.sub, fontFace: "Calibri",
  });

  footer(s, 3, false);
}

// ===========================================================================
// SLIDE 4 — Prompt Engineering + RAG
// ===========================================================================
{
  const s = baseSlide(COLORS.bgLight);
  s.addText("Prompt Engineering + RAG", { x: 0.6, y: 0.4, w: 9, h: 0.5, fontSize: 28, bold: true, color: COLORS.ink, fontFace: "Cambria" });
  s.addText("How answers stay grounded, safe, and empathetic", {
    x: 0.6, y: 0.9, w: 10.5, h: 0.35, fontSize: 12.5, color: COLORS.sub, fontFace: "Calibri",
  });

  // Left: Prompt engineering
  s.addShape("roundRect", { x: 0.6, y: 1.55, w: 5.9, h: 5.15, rectRadius: 0.1, fill: { color: COLORS.card }, line: { color: COLORS.border, width: 1 } });
  s.addShape("roundRect", { x: 0.6, y: 1.55, w: 5.9, h: 0.55, rectRadius: 0.1, fill: { color: COLORS.primary }, line: { type: "none" } });
  s.addShape("rect", { x: 0.6, y: 1.9, w: 5.9, h: 0.2, fill: { color: COLORS.primary }, line: { type: "none" } });
  s.addText("PROMPT ENGINEERING", { x: 0.9, y: 1.55, w: 5.3, h: 0.55, valign: "middle", fontSize: 13, bold: true, color: COLORS.white, charSpacing: 1, fontFace: "Calibri" });

  const promptRules = [
    ["Persona", "Friendly, empathetic, concise — \"Aarogya\""],
    ["Never diagnose", "No naming a condition the user \"has\""],
    ["Never prescribe / dose", "Redirects to a doctor or pharmacist"],
    ["Format contract", "Empathy line → info → self-care → consult line"],
    ["Injection-resistant", "Instructed to stay in character, ignore overrides"],
  ];
  let py = 2.3;
  promptRules.forEach((r) => {
    s.addShape("roundRect", { x: 0.9, y: py, w: 0.09, h: 0.72, fill: { color: COLORS.accent }, line: { type: "none" } });
    s.addText(r[0], { x: 1.1, y: py - 0.02, w: 5.2, h: 0.3, fontSize: 12.5, bold: true, color: COLORS.navy, fontFace: "Calibri" });
    s.addText(r[1], { x: 1.1, y: py + 0.28, w: 5.2, h: 0.4, fontSize: 10.3, color: COLORS.sub, fontFace: "Calibri" });
    py += 0.83;
  });

  // Right: RAG
  s.addShape("roundRect", { x: 6.8, y: 1.55, w: 5.9, h: 5.15, rectRadius: 0.1, fill: { color: COLORS.card }, line: { color: COLORS.border, width: 1 } });
  s.addShape("roundRect", { x: 6.8, y: 1.55, w: 5.9, h: 0.55, rectRadius: 0.1, fill: { color: COLORS.secondary }, line: { type: "none" } });
  s.addShape("rect", { x: 6.8, y: 1.9, w: 5.9, h: 0.2, fill: { color: COLORS.secondary }, line: { type: "none" } });
  s.addText("RETRIEVAL-AUGMENTED GENERATION", { x: 7.1, y: 1.55, w: 5.3, h: 0.55, valign: "middle", fontSize: 13, bold: true, color: COLORS.white, charSpacing: 0.6, fontFace: "Calibri" });

  const ragSteps = [
    "Docs chunked (~500 words, 75-word overlap)",
    "Embedded with all-MiniLM-L6-v2 (384-dim)",
    "Indexed in FAISS IndexFlatIP (cosine sim)",
    "Query embedded → top-4 chunks retrieved",
    "Chunks injected into prompt + cited to user",
  ];
  let ry = 2.3;
  ragSteps.forEach((r, i) => {
    s.addShape("ellipse", { x: 7.1, y: ry, w: 0.34, h: 0.34, fill: { color: COLORS.secondary }, line: { type: "none" } });
    s.addText(String(i + 1), { x: 7.1, y: ry, w: 0.34, h: 0.34, align: "center", valign: "middle", fontSize: 11, bold: true, color: COLORS.white, fontFace: "Calibri" });
    s.addText(r, { x: 7.58, y: ry + 0.02, w: 4.9, h: 0.4, fontSize: 11, color: COLORS.ink, fontFace: "Calibri" });
    ry += 0.62;
  });

  s.addShape("roundRect", { x: 7.1, y: 5.55, w: 5.3, h: 0.9, rectRadius: 0.08, fill: { color: "EAF7F3" }, line: { color: COLORS.accent, width: 1 } });
  s.addText("Sources: WHO · CDC · NIH · MedlinePlus-style reference docs on symptoms, nutrition, first aid & preventive care.", {
    x: 7.3, y: 5.62, w: 4.9, h: 0.76, fontSize: 9.8, color: "0B5E52", fontFace: "Calibri", lineSpacingMultiple: 1.2,
  });

  footer(s, 4, false);
}

// ===========================================================================
// SLIDE 5 — Future Improvements
// ===========================================================================
{
  const s = baseSlide(COLORS.navy);
  s.addShape("ellipse", { x: -2.2, y: 4.5, w: 5.5, h: 5.5, fill: { color: "0E3A45" }, line: { type: "none" } });

  s.addText("What's Next", { x: 0.7, y: 0.55, w: 8, h: 0.9, fontSize: 40, bold: true, color: COLORS.white, fontFace: "Cambria" });
  s.addText("Roadmap beyond the current MVP", {
    x: 0.7, y: 1.35, w: 8, h: 0.4, fontSize: 14, color: "CADCFC", fontFace: "Calibri",
  });

  const items = [
    ["🌐", "Multilingual support", "Translate input/output; language field already reserved in the API"],
    ["🎙️", "Voice input & speech output", "Speech-to-text and text-to-speech for hands-free use"],
    ["⚡", "Streaming responses", "Token-by-token replies over SSE/WebSocket for a snappier feel"],
    ["🧠", "LLM-based guardrail classifier", "Catch paraphrased risky requests regex rules miss"],
    ["🗄️", "Persistent memory", "Move session store to Redis/Postgres so history survives restarts"],
    ["📄", "PDF chat export", "Let users download a shareable medical-summary PDF of the conversation"],
  ];

  const cols = 3, cardW = 3.85, cardH = 2.15, gx = 0.28, gy = 0.28, startX = 0.7, startY = 2.05;
  items.forEach((it, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x = startX + col * (cardW + gx);
    const y = startY + row * (cardH + gy);
    s.addShape("roundRect", { x, y, w: cardW, h: cardH, rectRadius: 0.1, fill: { color: "0E2A44" }, line: { color: "1C3A5C", width: 1 } });
    s.addShape("ellipse", { x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55, fill: { color: COLORS.accent }, line: { type: "none" } });
    s.addText(it[0], { x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55, align: "center", valign: "middle", fontSize: 20, fontFace: "Calibri" });
    s.addText(it[1], { x: x + 0.25, y: y + 0.95, w: cardW - 0.5, h: 0.4, fontSize: 13, bold: true, color: COLORS.white, fontFace: "Calibri" });
    s.addText(it[2], { x: x + 0.25, y: y + 1.32, w: cardW - 0.5, h: 0.75, fontSize: 9.6, color: "AEB9CF", fontFace: "Calibri", lineSpacingMultiple: 1.2 });
  });

  footer(s, 5, true);
}

const OUTPUT_PATH = path.join(__dirname, "Aarogya_Architecture_Presentation.pptx");

pres.writeFile({ fileName: OUTPUT_PATH })
  .then(() => console.log(`PPTX written to ${OUTPUT_PATH}`))
  .catch((e) => { console.error(e); process.exit(1); });
