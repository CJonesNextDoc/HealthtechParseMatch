import json
import os
from typing import Any, Dict

from openai import AsyncAzureOpenAI

from .llm_adapter import LLMAdapter

# Env:
# AZURE_OPENAI_ENDPOINT=https://<your>.openai.azure.com
# AZURE_OPENAI_KEY=...
# AZURE_OPENAI_DEPLOYMENT=<your gpt-4o/4.1 etc deployment name>


class AzureOpenAIAdapter(LLMAdapter):
    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.key = os.getenv("AZURE_OPENAI_KEY", "")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

        if not self.endpoint or not self.key or not self.deployment:
            raise ValueError(
                "Azure OpenAI environment variables not set. "
                "Required: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT"
            )

        self.client = AsyncAzureOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
            api_key=self.key,
        )

    async def complete_json(self, system: str, user: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system + "\n\nRespond with a valid JSON object."},
                {"role": "user", "content": user},
            ],
            model=self.deployment,
            # response_format={"type": "json_object"},  # Removed for compatibility
            max_completion_tokens=16384,
        )
        content = response.choices[0].message.content
        print(f"LLM response content: {content}")  # Debug: print the raw content
        return json.loads(content)
