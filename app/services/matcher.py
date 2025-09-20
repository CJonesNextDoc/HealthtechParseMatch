from typing import List, Optional

from .scoring import MatchSignals, score


class Candidate(dict):
    # expected keys: patient_id, birthDate (YYYY-MM-DD), postalCode, telecom_last4?, family?, given?
    pass


class MatchResult(dict):
    status: str  # "none", "unique", "ambiguous"
    patient_id: Optional[str] = None  # if status=="unique"
    confidence: Optional[float] = None  # if status=="unique"
    reasons: Optional[List[str]] = None  # if status=="unique", list of signals that matched
    candidates: List[dict] = []  # if status=="ambiguous", list of {"patient_id":..., "confidence":...}
    next_best_signal: Optional[str] = None  # if status=="ambiguous", which signal to ask for next


class PatientMatcher:
    def __init__(self, fhir_client):
        self.fhir = fhir_client

    async def match(
        self,
        dob: str,
        zip: str,
        last4_phone: str | None = None,
        last_name_prefix: str | None = None,
        first_initial: str | None = None,
    ) -> MatchResult:
        # 1) Retrieve initial candidate set via FHIR search
        candidates = await self.fhir.search_patients(dob=dob, zip=zip)
        if not candidates:
            return MatchResult(status="none")

        # 2) Score candidates
        scored: List[tuple[float, Candidate]] = []
        for c in candidates:
            sig = MatchSignals(
                dob=(c.get("birthDate") == dob),
                zip_exact=(c.get("postalCode") == zip),
                zip_prefix=(c.get("postalCode", "").startswith(zip[:3])),
                last4_match=(last4_phone and c.get("telecom_last4") == last4_phone) or False,
                last_name_prefix=(last_name_prefix and c.get("family", "").lower().startswith(last_name_prefix.lower()))
                or False,
                first_initial=(first_initial and c.get("given", "").lower()[:1] == first_initial.lower()) or False,
            )
            scored.append((score(sig), c))

        scored.sort(key=lambda x: x[0], reverse=True)

        # 3) Decide unique / ambiguous
        if scored and (len(scored) == 1 or (scored[0][0] - scored[1][0] >= 0.15 and scored[0][0] >= 0.8)):
            best = scored[0]
            reasons = [
                k
                for k, v in MatchSignals(
                    **{**{f: False for f in MatchSignals.__annotations__.keys()}, **{}}
                ).__dict__.items()
                if v
            ]

            return MatchResult(status="unique", patient_id=best[1]["patient_id"], confidence=best[0], reasons=reasons)
        # else ambiguous
        return MatchResult(
            status="ambiguous",
            candidates=[{"patient_id": c[1]["patient_id"], "confidence": c[0]} for c in scored[:5]],
            next_best_signal=(
                "last4_phone" if any(not c[1].get("telecom_last4") for c in scored[:3]) else "last_name_prefix"
            ),
        )
