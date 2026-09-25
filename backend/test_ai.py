"""
RepoMind AIClient smoke test.

Usage
-----
Run from the backend/ directory:

    # Test placeholder (always works, no Ollama needed):
    python test_ai.py

    # Test Ollama (requires `ollama serve` and the model to be pulled):
    AI_PROVIDER=ollama python test_ai.py

Optional environment variables:
    OLLAMA_BASE_URL  — default: http://localhost:11434
    OLLAMA_MODEL     — default: qwen2.5-coder:7b
"""

import os
import sys

from app.ai.client import AIClient


def test_placeholder():
    """Placeholder provider must return a non-empty string."""

    os.environ["AI_PROVIDER"] = "placeholder"

    client = AIClient()
    response = client.generate("Find bugs in this repository.")

    assert isinstance(response, str), "Response must be a string."
    assert len(response.strip()) > 0, "Response must not be empty."

    print("[placeholder] PASSED")
    print(f"  response: {response.strip()}")


def test_ollama():
    """Ollama provider must connect and return a non-empty string."""

    os.environ["AI_PROVIDER"] = "ollama"

    client = AIClient()

    prompt = (
        "Reply with only a valid JSON object with a single key "
        "'status' set to 'ok'. No explanation, no markdown."
    )

    try:
        response = client.generate(prompt)
    except RuntimeError as error:
        print(f"[ollama] SKIPPED — Ollama unavailable: {error}")
        return

    assert isinstance(response, str), "Response must be a string."
    assert len(response.strip()) > 0, "Response must not be empty."

    print("[ollama] PASSED")
    print(f"  model:    {client.ollama_model}")
    print(f"  base_url: {client.ollama_base_url}")
    print(f"  response: {response.strip()[:200]}")


if __name__ == "__main__":
    provider = os.getenv("AI_PROVIDER", "placeholder")

    if provider == "ollama":
        test_ollama()
    else:
        test_placeholder()
        print()
        print("Tip: run with AI_PROVIDER=ollama to test the Ollama provider.")
