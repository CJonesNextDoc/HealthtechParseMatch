from typing import Any, Dict


class LLMAdapter:
    """Pluggable interface so you can swap Azure/Vertex/etc."""

    async def complete_json(self, system: str, user: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Implement in a provider adapter")
