from typing import Any, Dict, List, Optional

from .dob_llm_extractor import llm_dob_extract
from .dob_llm_reranker import llm_dob_rerank
from .llm_adapter import LLMAdapter


async def choose_dob_with_llm_guardrails(
    transcript_alternatives: List[str],
    parsed_candidates: List[Dict[str, Any]],  # [{"iso": "...", "score": 0.91}, ...]
    llm: LLMAdapter,
    accept_threshold: float = 0.80,
) -> Optional[Dict[str, Any]]:
    # Keep deterministic winner if clearly ahead
    if parsed_candidates and (
        len(parsed_candidates) == 1
        or (parsed_candidates[0]["score"] - parsed_candidates[1]["score"] >= 0.15 and parsed_candidates[0]["score"] >= 0.90)
    ):
        return {**parsed_candidates[0], "source": "deterministic"}

    # Rerank if you have >1 plausible candidates
    if parsed_candidates and len(parsed_candidates) > 1:
        best_transcript = transcript_alternatives[0] if transcript_alternatives else ""
        rerank = await llm_dob_rerank(
            transcript=best_transcript,
            candidates_iso=[c["iso"] for c in parsed_candidates[:5]],
            llm=llm,
            accept_threshold=accept_threshold,
        )
        if rerank:
            return rerank

    # Extract if you had none
    if not parsed_candidates:
        best_transcript = transcript_alternatives[0] if transcript_alternatives else ""
        extract = await llm_dob_extract(
            transcript=best_transcript,
            llm=llm,
            accept_threshold=accept_threshold,
        )
        if extract:
            return extract

    # Otherwise fall back to top deterministic guess
    return parsed_candidates[0] if parsed_candidates else None
