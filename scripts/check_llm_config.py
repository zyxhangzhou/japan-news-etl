"""Print resolved LLM settings (API key masked). Run from repo root: uv run python scripts/check_llm_config.py"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    load_dotenv()
    load_dotenv(root / ".env.local", override=True)

    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    base = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "(not set)"
    intent = os.getenv("LLM_INTENT_MODEL") or os.getenv("OPENAI_INTENT_MODEL") or "(not set)"
    answer = os.getenv("LLM_ANSWER_MODEL") or os.getenv("OPENAI_ANSWER_MODEL") or "(not set)"
    classifier = os.getenv("LLM_CLASSIFIER_MODEL") or os.getenv("OPENAI_CLASSIFIER_MODEL") or "(not set)"

    print("Resolved LLM configuration (after .env + .env.local)")
    print(f"  LLM_BASE_URL / OPENAI_BASE_URL -> {base}")
    print(f"  LLM_INTENT_MODEL (Java API)     -> {intent}")
    print(f"  LLM_ANSWER_MODEL (Java API)     -> {answer}")
    print(f"  LLM_CLASSIFIER_MODEL (Python)   -> {classifier}")
    if not key or key.startswith("your_"):
        print("  API key: NOT SET or placeholder")
    else:
        print(f"  API key: set (length {len(key)} chars)")

    issues: list[str] = []
    if "openai.com" in base and "gpt" not in classifier.lower() and "kimi" in classifier.lower():
        issues.append("base_url looks like OpenAI but classifier model looks like Kimi — check LLM_BASE_URL.")
    if "moonshot" in base and "gpt-4" in classifier.lower():
        issues.append("base_url is Moonshot/Kimi but model name looks like OpenAI — set kimi-k2-* models.")
    if issues:
        print("\nWarnings:")
        for item in issues:
            print(f"  - {item}")
    else:
        print("\nNo obvious URL/model mismatch detected.")


if __name__ == "__main__":
    main()
