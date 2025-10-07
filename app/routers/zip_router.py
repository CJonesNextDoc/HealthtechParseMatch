# app/routers/zip_router.py
from fastapi import APIRouter
from pydantic import BaseModel

from ..services.zip_parser import extract_zip5_candidates

router = APIRouter(prefix="/parse", tags=["parse"])


class ParseTranscripts(BaseModel):
    transcripts: list[str]


@router.post("/zip")
async def parse_zip(payload: ParseTranscripts):
    zip_pool: dict[str, float] = {}
    for transcript in payload.transcripts:
        cands = extract_zip5_candidates(transcript)
        for z, s in cands:
            zip_pool[z] = max(zip_pool.get(z, 0), s)

    # Sort by score descending, take top 5
    zip_cands = sorted(zip_pool.items(), key=lambda kv: -kv[1])[:5]
    return {"zip_candidates": [{"zip": z, "score": round(s, 3)} for z, s in zip_cands]}
