# app/routers/asr_router.py
from enum import Enum
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..clients.deepgram_client import deepgram_transcribe_nbest
from ..clients.transcribe_client import (
    start_job_with_alternatives,
    wait_for_job_and_fetch_alternatives,  # we'll define this below
)
from ..services.dob_parser import parse_dob_candidates
from ..services.zip_parser import extract_zip5_candidates

router = APIRouter(prefix="/asr", tags=["asr"])


class Provider(str, Enum):
    deepgram = "deepgram"
    aws = "aws"


class IngestOut(BaseModel):
    provider: Provider
    nbest: List[str] = Field(default_factory=list)
    dob_candidates: List[dict] = Field(default_factory=list)
    zip_candidates: List[dict] = Field(default_factory=list)


@router.post("/ingest", response_model=IngestOut)
async def ingest(
    provider: Provider,
    file: UploadFile = File(...),
    alternatives: int = 5,
    numerals: bool = True,
    allow_plus4: bool = False,
):
    audio = await file.read()

    if provider == Provider.deepgram:
        nbest = await deepgram_transcribe_nbest(audio, alternatives=alternatives, numerals=numerals)

    elif provider == Provider.aws:
        # For AWS example we assume you've staged the file in S3 separately.
        # If you prefer direct upload, stream to S3 here and pass its URI.
        try:
            nbest = wait_for_job_and_fetch_alternatives(
                start_job_with_alternatives, audio_bytes=audio, max_alts=alternatives
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"AWS Transcribe error: {e}")

    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    # Merge candidates from all alts
    dob_pool: dict[str, float] = {}
    zip_pool: dict[str, float] = {}
    for rank, hyp in enumerate(nbest):
        # slight decay by alt rank to prefer top hypotheses
        decay = 0.02 * rank

        dob_result = parse_dob_candidates(hyp)
        for cand in dob_result["dob_candidates"]:
            iso = cand["iso"]
            s = cand["score"]
            dob_pool[iso] = max(dob_pool.get(iso, 0), s - decay)

        for z, s in extract_zip5_candidates(hyp, allow_plus4=allow_plus4):
            zip_pool[z] = max(zip_pool.get(z, 0), s - decay)

    dob_cands = sorted(dob_pool.items(), key=lambda kv: -kv[1])[:5]
    zip_cands = sorted(zip_pool.items(), key=lambda kv: -kv[1])[:5]

    return IngestOut(
        provider=provider,
        nbest=nbest,
        dob_candidates=[{"iso": d, "score": round(s, 3)} for d, s in dob_cands],
        zip_candidates=[{"zip": z, "score": round(s, 3)} for z, s in zip_cands],
    )
