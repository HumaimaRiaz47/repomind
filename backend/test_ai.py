from app.ai.client import AIClient


client = AIClient()

response = client.generate(
    "Find bugs in this repository."
)

print(response)