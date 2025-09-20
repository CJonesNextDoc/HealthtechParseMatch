import os

from fastapi import APIRouter
from pydantic import BaseModel

from ..clients.fhir_client import FHIRClient
from ..services.matcher import PatientMatcher

router = APIRouter(prefix="/patient", tags=["patient"])


class MatchIn(BaseModel):
    dob: str
    zip: str
    last4_phone: str | None = None
    last_name_prefix: str | None = None
    first_initial: str | None = None


@router.post("/match")
async def match_patient(payload: MatchIn):
    fc = FHIRClient(base_url=os.environ.get("FHIR_BASE_URL", ""), token=os.environ.get("FHIR_BEARER_TOKEN"))
    matcher = PatientMatcher(fc)
    return await matcher.match(**payload.model_dump())
