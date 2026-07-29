"""
Global pytest configuration. Ensures tests run without requiring live LLM
API keys or the heavier optional RAG dependencies (torch / faiss) to be
installed, by defaulting RAG off and clearing any LLM key picked up from
the environment before the app modules are imported.
"""

import os

os.environ.setdefault("RAG_ENABLED", "false")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ENVIRONMENT", "development")
