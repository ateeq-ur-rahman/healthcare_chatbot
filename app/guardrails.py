"""Rule-based safety layer, applied both before and after the LLM call.

Two responsibilities:

1. Input screening - classify the raw user message for things the
   assistant must never act on directly (diagnosis requests, dosage or
   prescription requests, illegal-drug advice, prompt injection/leak
   attempts), and for medical or mental-health emergencies that need an
   immediate, deterministic reply instead of an LLM-generated one.
2. Output screening - a second pass over the LLM's own response, to catch
   the rare case where it drifts into diagnosing or naming a dose despite
   the system prompt telling it not to.

This is regex/keyword-based rather than a second LLM call on purpose: it's
fast, deterministic, unit-testable without network access, and - unlike a
classifier LLM - can't itself be talked out of doing its job by a cleverly
worded message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models import GuardrailFlag
from app.utils import get_logger

logger = get_logger(__name__)


def _compile(*patterns: str) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


# Emergency phrasing is grouped by clinical category so the log line for a
# detected emergency tells you *which* one fired, not just that one did.
EMERGENCY_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "chest_pain": _compile(r"\bchest\s+pain\b", r"\btightness\s+in\s+(my\s+)?chest\b"),
    "difficulty_breathing": _compile(
        r"\bcan'?t\s+breathe\b", r"\bdifficulty\s+breathing\b",
        r"\bshortness\s+of\s+breath\b", r"\bgasping\s+for\s+air\b",
    ),
    "stroke": _compile(
        r"\bface\s+(is\s+)?drooping\b", r"\bslurred\s+speech\b",
        r"\bsudden\s+numbness\b", r"\bsudden\s+weakness\s+(on\s+)?one\s+side\b",
        r"\bstroke\s+symptoms?\b",
    ),
    "suicidal_ideation": _compile(
        r"\bkill\s+myself\b", r"\bsuicid(e|al)\b", r"\bend\s+my\s+life\b",
        r"\bwant\s+to\s+die\b", r"\bdon'?t\s+want\s+to\s+live\b", r"\bself[\s-]?harm\b",
    ),
    "severe_bleeding": _compile(
        r"\bsevere\s+bleeding\b", r"\bbleeding\s+(won'?t|will\s+not)\s+stop\b", r"\bheavy\s+blood\s+loss\b",
    ),
    "loss_of_consciousness": _compile(
        r"\bpassed\s+out\b", r"\bunconscious\b", r"\bloss\s+of\s+consciousness\b", r"\bnot\s+waking\s+up\b",
    ),
    "anaphylaxis": _compile(r"\banaphylax", r"\bthroat\s+(is\s+)?closing\b", r"\bsevere\s+allergic\s+reaction\b"),
}

DIAGNOSIS_PATTERNS = _compile(
    r"\bdo\s+i\s+have\b", r"\bwhat\s+disease\s+do\s+i\s+have\b",
    r"\bam\s+i\s+(having|suffering\s+from)\b", r"\bdiagnos(e|is)\s+me\b",
    r"\bwhat'?s\s+wrong\s+with\s+me\b", r"\bis\s+this\s+cancer\b", r"\btell\s+me\s+what\s+i\s+have\b",
)

DOSAGE_PATTERNS = _compile(
    r"\bhow\s+many\s+(mg|milligrams?|pills?|tablets?)\b",
    r"\bwhat\s+dose\b", r"\bwhat\s+dosage\b", r"\bhow\s+much\s+should\s+i\s+take\b", r"\bmax(imum)?\s+dose\b",
)

PRESCRIPTION_PATTERNS = _compile(
    r"\bprescribe\b", r"\bwrite\s+me\s+a\s+prescription\b",
    r"\bwhat\s+medication\s+should\s+i\s+take\b", r"\bwhich\s+antibiotic\s+should\s+i\s+take\b",
)

ILLEGAL_DRUG_PATTERNS = _compile(
    r"\bhow\s+to\s+(make|synthesize|cook)\s+(meth|cocaine|heroin|mdma|lsd)\b",
    r"\bbuy\s+(illegal\s+)?drugs?\s+online\b", r"\bget\s+high\s+on\b", r"\brecreational\s+dose\s+of\b",
)

PROMPT_INJECTION_PATTERNS = _compile(
    r"\bignore\s+(all\s+)?(previous|prior|above)\s+instructions\b",
    r"\byou\s+are\s+now\s+(a|an)\b", r"\bdisregard\s+your\s+(system\s+)?prompt\b",
    r"\bact\s+as\s+(if\s+you\s+(are|were)|a)\b.{0,30}\b(doctor|dan|jailbreak)\b",
    r"\bpretend\s+(you\s+are|to\s+be)\b", r"\boverride\s+your\s+(guidelines|instructions|rules)\b",
)

PROMPT_LEAK_PATTERNS = _compile(
    r"\bshow\s+me\s+your\s+system\s+prompt\b", r"\bwhat\s+(are|is)\s+your\s+instructions\b",
    r"\brepeat\s+the\s+(text|prompt)\s+above\b", r"\breveal\s+your\s+(prompt|instructions)\b",
)

# Defense in depth: catches the LLM's own text slipping past the system prompt.
OUTPUT_DIAGNOSIS_PATTERNS = _compile(
    r"\byou\s+have\s+(a|an)\s+\w+", r"\byou\s+are\s+suffering\s+from\b", r"\byour\s+diagnosis\s+is\b",
)
OUTPUT_DOSAGE_PATTERNS = _compile(
    r"\btake\s+\d+\s?(mg|ml|milligrams?)\b", r"\b\d+\s?mg\s+(twice|once|three\s+times)\s+a\s+day\b",
)

EMERGENCY_RESPONSE = (
    "🚨 **This sounds like it could be a medical emergency.**\n\n"
    "Please **call your local emergency number right now** (e.g., 108 / 112 in India, "
    "911 in the US, 999 in the UK) or go to the nearest emergency room immediately. "
    "If someone else is with you, ask them to stay with you and help you get "
    "emergency care.\n\n"
    "If you are having thoughts of suicide or self-harm, please reach out right now to "
    "a crisis line — in India you can call the **Tele-MANAS helpline at 14416** or "
    "**iCall at 9152987821**, available 24/7. You do not have to go through this alone.\n\n"
    "I'm an AI assistant and can't provide emergency medical care myself, so please "
    "prioritize contacting a real person or emergency service right now."
)

INJECTION_RESPONSE = (
    "I can't ignore or override my safety guidelines, and I don't share my internal "
    "system instructions. I'm happy to keep helping with general health, nutrition, "
    "or wellness questions though — what would you like to know?"
)

ILLEGAL_DRUG_RESPONSE = (
    "I can't help with that. If you're dealing with substance use and would "
    "like support, a doctor, de-addiction counselor, or a helpline like "
    "India's National Drug Helpline can help safely. Is there something else "
    "about health or wellness I can help with?"
)


@dataclass
class GuardrailResult:
    """Outcome of running the input-side checks on one user message."""

    flags: list[GuardrailFlag] = field(default_factory=list)
    is_emergency: bool = False
    emergency_types: list[str] = field(default_factory=list)
    blocked: bool = False
    override_response: str | None = None

    def block(self, flag: GuardrailFlag, response: str) -> None:
        """Mark this message as blocked, to be answered without calling the LLM."""
        self.flags.append(flag)
        self.blocked = True
        self.override_response = response


def _any_pattern_matches(text: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def check_input(message: str) -> GuardrailResult:
    """Screen a raw user message before it reaches the LLM.

    Emergencies are checked first and, if found, short-circuit every other
    check - a message that mentions both chest pain and a dosage question
    should get emergency guidance, not a dosage disclaimer.
    """
    result = GuardrailResult()

    for emergency_type, patterns in EMERGENCY_PATTERNS.items():
        if _any_pattern_matches(message, patterns):
            result.is_emergency = True
            result.emergency_types.append(emergency_type)

    if result.is_emergency:
        result.flags.append(GuardrailFlag.MEDICAL_EMERGENCY)
        if "suicidal_ideation" in result.emergency_types:
            result.flags.append(GuardrailFlag.MENTAL_HEALTH_CRISIS)
        result.blocked = True
        result.override_response = EMERGENCY_RESPONSE
        logger.warning("emergency_detected", extra={"emergency_types": result.emergency_types})
        return result

    if _any_pattern_matches(message, PROMPT_INJECTION_PATTERNS):
        result.block(GuardrailFlag.PROMPT_INJECTION, INJECTION_RESPONSE)

    if _any_pattern_matches(message, PROMPT_LEAK_PATTERNS):
        result.block(GuardrailFlag.PROMPT_LEAK_ATTEMPT, INJECTION_RESPONSE)

    if _any_pattern_matches(message, ILLEGAL_DRUG_PATTERNS):
        result.block(GuardrailFlag.ILLEGAL_DRUG_ADVICE, ILLEGAL_DRUG_RESPONSE)

    # These are advisory only - flagged so the system prompt can steer the
    # LLM's response, but not blocked, since a natural-language redirect
    # ("I can't diagnose you, but here's what commonly causes...") is more
    # useful than a canned refusal for borderline phrasing.
    if _any_pattern_matches(message, DIAGNOSIS_PATTERNS):
        result.flags.append(GuardrailFlag.DIAGNOSIS_REQUEST)

    if _any_pattern_matches(message, DOSAGE_PATTERNS):
        result.flags.append(GuardrailFlag.MEDICATION_DOSAGE)

    if _any_pattern_matches(message, PRESCRIPTION_PATTERNS):
        result.flags.append(GuardrailFlag.PRESCRIPTION_REQUEST)

    if result.flags:
        logger.info("guardrail_flags_raised", extra={"flags": [f.value for f in result.flags]})

    return result


def check_output(text: str) -> list[GuardrailFlag]:
    """Sweep the LLM's generated response for language it shouldn't have used."""
    flags: list[GuardrailFlag] = []
    if _any_pattern_matches(text, OUTPUT_DIAGNOSIS_PATTERNS):
        flags.append(GuardrailFlag.DIAGNOSIS_REQUEST)
    if _any_pattern_matches(text, OUTPUT_DOSAGE_PATTERNS):
        flags.append(GuardrailFlag.MEDICATION_DOSAGE)
    if flags:
        logger.warning("output_guardrail_triggered", extra={"flags": [f.value for f in flags]})
    return flags


def sanitize_output(text: str) -> str:
    """Strip any dosage figure that slipped through and flag it to the user.

    This is a last-resort safety net, not a substitute for prompting the
    model correctly in the first place.
    """
    if not check_output(text):
        return text
    cleaned = OUTPUT_DOSAGE_PATTERNS[0].sub(
        "take a dose recommended by your doctor or pharmacist", text
    )
    note = (
        "\n\n_Note: I removed a specific dosage figure from this response — "
        "please get exact dosing from a doctor or pharmacist._"
    )
    return cleaned + note
