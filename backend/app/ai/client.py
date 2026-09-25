import os

import requests
from dotenv import load_dotenv

load_dotenv()


class AIClient:

    def __init__(self):
        self.provider = os.getenv(
            "AI_PROVIDER",
            "placeholder"
        )
        self.ollama_base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://localhost:11434"
        )
        self.ollama_model = os.getenv(
            "OLLAMA_MODEL",
            "qwen2.5-coder:7b"
        )

    def generate(self, prompt: str) -> str:

        if self.provider == "placeholder":
            return """
{
    "findings": []
}
"""

        if self.provider == "ollama":
            return self._generate_ollama(prompt)

        raise NotImplementedError(
            f"AI provider '{self.provider}' "
            "has not been configured yet."
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_ollama(self, prompt: str) -> str:
        """
        Send a prompt to a locally running Ollama instance and return
        the model's response text.

        Raises RuntimeError if Ollama is unreachable or returns an error.
        """

        url = f"{self.ollama_base_url}/api/generate"

        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=120,
            )
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Could not connect to Ollama at '{self.ollama_base_url}'. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(
                f"Ollama request timed out after 120 seconds "
                f"(model: {self.ollama_model})."
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama returned HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        data = response.json()

        return data.get("response", "")