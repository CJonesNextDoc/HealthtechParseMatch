from typing import Any, Dict, List, Optional

from .llm_adapter import LLMAdapter
from .llm_utils import redact_phi, validate_json, within_age_window

DOB_RERANK_SCHEMA = {
    "type": "object",
    "properties": {
        "chosen_index": {"type": ["integer", "null"], "minimum": 0},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "justification": {"type": "string"},
    },
    "required": ["chosen_index", "confidence"],
    "additionalProperties": False,
}

SYS = (
    "You are a judge. Choose which DOB candidate is exactly supported by the transcript words. "
    "Pick only from the provided list. If none is supported, choose null."
)
USR_TMPL = (
    'Transcript:\n"""\n{t}\n"""\n\n'
    "Candidates (index: ISO):\n{cands}\n\n"
    "Rules:\n"
    "1) Choose the index explicitly supported by the transcript.\n"
    "2) If none is clearly supported, chosen_index=null and confidence=0.\n"
    "3) Return strict JSON only."
)


def _fmt(cands: List[str]) -> str:
    return "\n".join(f"{i}: {x}" for i, x in enumerate(cands))


async def llm_dob_rerank(
    transcript: str, candidates_iso: List[str], llm: LLMAdapter, min_age=0, max_age=120, accept_threshold=0.8
) -> Optional[Dict[str, Any]]:
    safe = redact_phi(transcript)
    raw = await llm.complete_json(SYS, USR_TMPL.format(t=safe, cands=_fmt(candidates_iso)), DOB_RERANK_SCHEMA)
    try:
        out = validate_json(raw, DOB_RERANK_SCHEMA)
    except Exception:
        return None
    idx, conf = out.get("chosen_index"), float(out.get("confidence") or 0)
    if idx is None or conf < accept_threshold:
        return None
    if not (0 <= idx < len(candidates_iso)):
        return None
    iso = candidates_iso[idx]
    if not within_age_window(iso, min_age=min_age, max_age=max_age):
        return None
    return {"iso": iso, "score": conf, "source": "llm_reranker", "index": idx}
