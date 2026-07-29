"""
Unit tests for the dependency-light parts of app.rag (chunking + header
parsing). Embedding/FAISS-dependent code paths are covered separately and
require the optional sentence-transformers / faiss packages to be
installed (see tests/test_rag_integration.py).
"""

from app.rag import _parse_doc_header, chunk_text


def test_chunk_text_basic_split():
    text = " ".join(f"word{i}" for i in range(100))
    chunks = chunk_text(text, chunk_size=20, overlap=5)
    assert len(chunks) > 1
    # First chunk should have exactly 20 words
    assert len(chunks[0].split()) == 20


def test_chunk_text_overlap():
    text = " ".join(f"word{i}" for i in range(50))
    chunks = chunk_text(text, chunk_size=20, overlap=5)
    first_words = chunks[0].split()
    second_words = chunks[1].split()
    # Last 5 words of chunk 1 should match first 5 words of chunk 2
    assert first_words[-5:] == second_words[:5]


def test_chunk_text_short_text_single_chunk():
    chunks = chunk_text("short text here", chunk_size=500, overlap=50)
    assert len(chunks) == 1


def test_chunk_text_empty():
    assert chunk_text("", 500, 50) == []


def test_parse_doc_header_with_metadata():
    raw = "TITLE: Fever Basics\nSOURCE: CDC\n---\nBody text here."
    title, source, body = _parse_doc_header(raw, fallback_title="fallback")
    assert title == "Fever Basics"
    assert source == "CDC"
    assert body.strip() == "Body text here."


def test_parse_doc_header_without_metadata_uses_fallback():
    raw = "Just plain body text with no header."
    title, source, body = _parse_doc_header(raw, fallback_title="my_file")
    assert title == "my_file"
    assert source == "Knowledge Base"
    assert body == raw
