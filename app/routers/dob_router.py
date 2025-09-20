from fastapi import APIRouter
from pydantic import BaseModel

# from ..services.dob_zip_parser import extract_zip_candidates, parse_dob_candidates
from ..services.dob_parser import parse_dob_candidates

router = APIRouter(prefix="/parse", tags=["parse"])


class ParseIn(BaseModel):
    text: str
    date_floor: int | None = None
    date_ceiling: int | None = None


@router.post("/dob")
async def parse_dob(payload: ParseIn):
    dob = parse_dob_candidates(payload.text, max_age=100)
    # zc = extract_zip_candidates(payload.text)
    # return {"dob_candidates": [{"iso": d[0], "score": d[1]} for d in dob],
    #         "zip_candidates": [{"zip": z, "score": 0.9} for z in zc]}
    # return {"dob_candidates": [{"iso": d[0], "score": d[1]} for d in dob]}
    return dob
