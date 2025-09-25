from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.azure_openai_adapter import AzureOpenAIAdapter
from app.services.dob_pipeline import choose_dob_with_llm_guardrails

router = APIRouter(prefix="/dob", tags=["dob"])


class ChooseIn(BaseModel):
    alternatives: List[str]
    parsed_candidates: List[Dict[str, Any]] = []


class ChooseOut(BaseModel):
    winner: Optional[Dict[str, Any]]
    used_llm: bool


@router.post("/choose", response_model=ChooseOut)
async def choose(payload: ChooseIn):
    try:
        llm = AzureOpenAIAdapter()
    except KeyError as e:
        raise HTTPException(status_code=500, detail=f"Missing env for Azure OpenAI: {e}")

    winner = await choose_dob_with_llm_guardrails(
        transcript_alternatives=payload.alternatives,
        parsed_candidates=payload.parsed_candidates,
        llm=llm,
        accept_threshold=0.80,
    )
    return ChooseOut(winner=winner, used_llm=winner is not None and winner.get("source") != "deterministic")
