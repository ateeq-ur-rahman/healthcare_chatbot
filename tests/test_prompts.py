"""Unit tests for app.prompts."""

from app.models import SourceDocument
from app.prompts import SYSTEM_PROMPT, build_user_turn, format_context


def test_system_prompt_contains_key_safety_rules():
    lowered = SYSTEM_PROMPT.lower()
    assert "never diagnose" in lowered or "diagnose a disease" in lowered
    assert "prescribe" in lowered
    assert "dosage" in lowered
    assert "consult" in lowered


def test_format_context_empty():
    result = format_context([])
    assert "no specific reference" in result.lower()


def test_format_context_with_sources():
    sources = [SourceDocument(title="Fever Basics", source="CDC", snippet="Fever is...")]
    result = format_context(sources)
    assert "Fever Basics" in result
    assert "CDC" in result


def test_build_user_turn_includes_question_and_context():
    sources = [SourceDocument(title="Hydration", source="NIH", snippet="Drink water...")]
    prompt = build_user_turn("How much water should I drink?", sources)
    assert "How much water should I drink?" in prompt
    assert "Hydration" in prompt
