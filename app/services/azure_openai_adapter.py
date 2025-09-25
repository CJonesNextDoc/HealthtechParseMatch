import json
import os
from typing import Any, Dict

import httpx

from .llm_adapter import LLMAdapter

# Env:
# AZURE_OPENAI_ENDPOINT=https://<your>.openai.azure.com
# AZURE_OPENAI_KEY=...
# AZURE_OPENAI_DEPLOYMENT=<your gpt-4o/4.1 etc deployment name>


class AzureOpenAIAdapter(LLMAdapter):
    def __init__(self):
        self.endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
        self.key = os.environ["AZURE_OPENAI_KEY"]
        self.deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    async def complete_json(self, system: str, user: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"api-key": self.key, "Content-Type": "application/json"}
        payload = {
            "model": self.deployment,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # Ask Azure for a JSON object response
            "response_format": {"type": "json_object"},
            # (Optional) you can also pass a tool/json_schema when you move to structured outputs
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}",
                headers=headers,
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
