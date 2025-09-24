from fastapi import APIRouter
from pydantic import BaseModel

from app.utils.logger import get_logger
from app.utils.logging_config import setup_logging

# from ..services.dob_zip_parser import extract_zip_candidates, parse_dob_candidates
from ..services.dob_parser import parse_dob_candidates

# Configure logging
setup_logging(log_level="DEBUG")
logger = get_logger(__name__)


router = APIRouter(prefix="/parse", tags=["parse"])


class ParseIn(BaseModel):
    text: str


class ParseTranscripts(BaseModel):
    transcripts: list[str]


@router.post("/dob")
async def parse_dob(payload: ParseTranscripts):
    dob_pool: dict[str, float] = {}
    for transcript in payload.transcripts:
        logger.debug("Parsing DOB from transcript: %s", transcript)
        result = parse_dob_candidates(transcript, max_age=100)
        for candidate in result.get("dob_candidates", []):
            iso = candidate.get("iso")
            score = candidate.get("score", 0)
            if iso:
                dob_pool[iso] = max(dob_pool.get(iso, 0), score)

    # Sort by score descending, take top 5
    dob_cands = sorted(dob_pool.items(), key=lambda kv: -kv[1])[:5]
    return {"dob_candidates": [{"iso": iso, "score": round(score, 3)} for iso, score in dob_cands]}
