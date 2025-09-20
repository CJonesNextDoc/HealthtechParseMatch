# app/routers/zip_router.py
from fastapi import APIRouter
from pydantic import BaseModel

from ..services.zip_parser import extract_zip5_candidates

router = APIRouter(prefix="/parse", tags=["parse"])


class ZipIn(BaseModel):
    text: str
    allow_plus4: bool = False


@router.post("/zip")
async def parse_zip(payload: ZipIn):
    cands = extract_zip5_candidates(payload.text, allow_plus4=payload.allow_plus4)
    return {"zip_candidates": [{"zip": z, "score": s} for z, s in cands]}
