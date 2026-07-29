"""Retrieval-Augmented Generation pipeline.

    knowledge_base/docs/*.txt|*.md
        -> chunk_text()
        -> embeddings.embed_texts()
        -> FAISS IndexFlatIP
        -> persisted under vectorstore/ (index + JSON metadata sidecar)

At query time, `retrieve()` embeds the user's question and returns the
top-k most similar chunks as `SourceDocument`s, which get injected into
the prompt as grounding context and shown to the user as citations.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.embeddings import embed_query, embed_texts
from app.models import SourceDocument
from app.utils import get_logger

logger = get_logger(__name__)

INDEX_FILENAME = "index.faiss"
METADATA_FILENAME = "metadata.json"
KNOWLEDGE_BASE_EXTENSIONS = ("*.txt", "*.md")
SNIPPET_MAX_CHARS = 500


@dataclass
class Chunk:
    """One embedded, citable slice of a knowledge-base document."""

    chunk_id: int
    text: str
    title: str
    source: str


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping word-count chunks.

    A simple whitespace splitter is used on purpose: it's dependency-free,
    predictable, and good enough for short/medium reference documents like
    WHO/CDC fact sheets. Swap in a token-aware splitter (e.g. tiktoken) if
    documents grow much larger or token budgets get tight.
    """
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    words = normalized.split(" ")
    step = max(chunk_size - overlap, 1)
    chunks = []
    for start in range(0, len(words), step):
        window = words[start : start + chunk_size]
        if not window:
            continue
        chunks.append(" ".join(window))
        if start + chunk_size >= len(words):
            break
    return chunks


def _parse_doc_header(raw_text: str, fallback_title: str) -> tuple[str, str, str]:
    """Split an optional `TITLE:` / `SOURCE:` header off the document body.

    Documents may start with:

        TITLE: Fever in Adults
        SOURCE: CDC
        ---
        <body text>

    Falls back to a filename-derived title and "Knowledge Base" as the
    source when no header is present.
    """
    if not raw_text.startswith("TITLE:"):
        return fallback_title, "Knowledge Base", raw_text

    lines = raw_text.split("\n")
    header_lines: list[str] = []
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            body_start = i + 1
            break
        header_lines.append(line)

    header_text = "\n".join(header_lines)
    title_match = re.search(r"TITLE:\s*(.+)", header_text)
    source_match = re.search(r"SOURCE:\s*(.+)", header_text)

    title = title_match.group(1).strip() if title_match else fallback_title
    source = source_match.group(1).strip() if source_match else "Knowledge Base"
    body = "\n".join(lines[body_start:])
    return title, source, body


def _load_chunks_from_directory(docs_dir: Path) -> list[Chunk]:
    """Read every knowledge-base document, chunk it, and assign chunk ids."""
    files = sorted(
        path for pattern in KNOWLEDGE_BASE_EXTENSIONS for path in docs_dir.glob(pattern)
    )
    if not files:
        logger.warning("no_knowledge_base_documents_found", extra={"dir": str(docs_dir)})
        return []

    chunks: list[Chunk] = []
    for file_path in files:
        title, source, body = _parse_doc_header(
            file_path.read_text(encoding="utf-8"), fallback_title=file_path.stem
        )
        for piece in chunk_text(body, settings.chunk_size, settings.chunk_overlap):
            chunks.append(Chunk(chunk_id=len(chunks), text=piece, title=title, source=source))
    return chunks


class VectorStore:
    """FAISS-backed similarity index over embedded knowledge-base chunks."""

    def __init__(self, persist_dir: Path | str | None = None):
        self.persist_dir = Path(persist_dir or settings.vectorstore_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._index = None
        self._chunks: list[Chunk] = []

    def build_from_directory(self, docs_dir: Path | str | None = None) -> int:
        """(Re)build the index in memory from the knowledge-base source files.

        Returns the number of chunks indexed. Does not persist to disk -
        call `save()` afterwards if the result should survive a restart.
        """
        import faiss

        chunks = _load_chunks_from_directory(Path(docs_dir or settings.knowledge_base_dir))
        if not chunks:
            logger.warning("vectorstore_build_skipped_no_chunks")
            self._chunks = []
            self._index = None
            return 0

        vectors = embed_texts([chunk.text for chunk in chunks])
        index = faiss.IndexFlatIP(vectors.shape[1])  # normalized vectors -> inner product = cosine
        index.add(vectors)

        self._index = index
        self._chunks = chunks
        logger.info("vectorstore_built", extra={"num_chunks": len(chunks), "dim": vectors.shape[1]})
        return len(chunks)

    def save(self) -> None:
        """Persist the current index and chunk metadata to `self.persist_dir`."""
        import faiss

        if self._index is None:
            logger.warning("save_skipped_no_index_built")
            return

        faiss.write_index(self._index, str(self.persist_dir / INDEX_FILENAME))
        metadata = [
            {"chunk_id": c.chunk_id, "text": c.text, "title": c.title, "source": c.source}
            for c in self._chunks
        ]
        (self.persist_dir / METADATA_FILENAME).write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("vectorstore_saved", extra={"dir": str(self.persist_dir)})

    def load(self) -> bool:
        """Load a previously persisted index. Returns False if none exists yet."""
        import faiss

        index_path = self.persist_dir / INDEX_FILENAME
        metadata_path = self.persist_dir / METADATA_FILENAME
        if not index_path.exists() or not metadata_path.exists():
            return False

        self._index = faiss.read_index(str(index_path))
        raw_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self._chunks = [Chunk(**entry) for entry in raw_metadata]
        logger.info("vectorstore_loaded", extra={"num_chunks": len(self._chunks)})
        return True

    @property
    def is_loaded(self) -> bool:
        return self._index is not None and len(self._chunks) > 0

    def search(self, query: str, top_k: int) -> list[SourceDocument]:
        """Return the top-k chunks most similar to `query`, as citable SourceDocuments."""
        if not self.is_loaded:
            return []

        query_vector = embed_query(query).reshape(1, -1)
        scores, indices = self._index.search(query_vector, min(top_k, len(self._chunks)))

        results: list[SourceDocument] = []
        for score, chunk_index in zip(scores[0], indices[0]):
            if chunk_index < 0:  # FAISS pads short result sets with -1
                continue
            chunk = self._chunks[chunk_index]
            results.append(
                SourceDocument(
                    title=chunk.title,
                    source=chunk.source,
                    snippet=chunk.text[:SNIPPET_MAX_CHARS],
                    score=float(score),
                )
            )
        return results


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Process-wide singleton VectorStore, building the index on first use if needed."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        if not _vector_store.load():
            logger.info("no_persisted_vectorstore_building_now")
            _vector_store.build_from_directory()
            _vector_store.save()
    return _vector_store


def retrieve(query: str, top_k: int | None = None) -> list[SourceDocument]:
    """Fetch grounding context for a user query. Returns [] when RAG is disabled."""
    if not settings.rag_enabled:
        return []
    return get_vector_store().search(query, top_k or settings.rag_top_k)


if __name__ == "__main__":
    # `python -m app.rag` - (re)builds and persists the vector store from the CLI.
    store = VectorStore()
    indexed_count = store.build_from_directory()
    store.save()
    print(f"Indexed {indexed_count} chunks from {settings.knowledge_base_dir} into {settings.vectorstore_dir}")
