from typing import Any, Dict, Optional

from .llm_adapter import LLMAdapter
from .llm_utils import redact_phi, validate_json, within_age_window

DOB_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "dob_iso": {"type": ["string", "null"], "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
    "required": ["dob_iso", "confidence"],
    "additionalProperties": False,
}

SYS = (
    "Extract a patient's date of birth ONLY if explicit and unambiguous. "
    "Return strict JSON matching the schema. No extra text."
)
USR_TMPL = (
    'Transcript:\n"""\n{t}\n"""\n\n'
    "If DOB is clearly present, output dob_iso in YYYY-MM-DD and a confidence [0,1]. "
    "If ambiguous or partial, set dob_iso=null and confidence=0."
)


async def llm_dob_extract(
    transcript: str, llm: LLMAdapter, min_age=0, max_age=120, accept_threshold=0.8
) -> Optional[Dict[str, Any]]:
    safe = redact_phi(transcript)
    raw = await llm.complete_json(SYS, USR_TMPL.format(t=safe), DOB_EXTRACT_SCHEMA)
    try:
        out = validate_json(raw, DOB_EXTRACT_SCHEMA)
    except Exception:
        return None
    dob, conf = out.get("dob_iso"), float(out.get("confidence") or 0)
    if dob is None or conf < accept_threshold:
        return None
    if not within_age_window(dob, min_age=min_age, max_age=max_age):
        return None
    return {"iso": dob, "score": conf, "source": "llm_extractor"}
