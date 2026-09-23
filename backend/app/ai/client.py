import os

from dotenv import load_dotenv

load_dotenv()


class AIClient:

    def __init__(self):
        self.provider = os.getenv(
            "AI_PROVIDER",
            "placeholder"
        )

    def generate(self, prompt: str) -> str:

        if self.provider == "placeholder":
            return """
{
    "findings": []
}
"""

        raise NotImplementedError(
            f"AI provider '{self.provider}' "
            "has not been configured yet."
        )