from typing import Dict, List

import httpx


class FHIRClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    async def search_patients(self, *, dob: str, zip: str) -> List[Dict]:
        # Minimal FHIR Patient search: birthdate + postal-code; adapt per EHR
        # GET /Patient?birthdate=eqYYYY-MM-DD&address-postalcode=NNNNN
        params = {"birthdate": f"eq{dob}", "address-postalcode": zip}
        headers = {"Accept": "application/fhir+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/Patient", params=params, headers=headers)
            r.raise_for_status()
            bundle = r.json()
        out = []
        for e in bundle.get("entry", []):
            p = e.get("resource", {})
            telecoms = "".join(t.get("value", "") for t in p.get("telecom", []) if t.get("system") == "phone")
            last4 = telecoms[-4:] if telecoms and telecoms[-4:].isdigit() else None
            postal = None
            for addr in p.get("address", []) or []:
                if "postalCode" in addr:
                    postal = addr["postalCode"]
                    break
            out.append(
                {
                    "patient_id": p.get("id"),
                    "birthDate": p.get("birthDate"),
                    "postalCode": postal,
                    "telecom_last4": last4,
                    "family": (p.get("name", [{}])[0].get("family") if p.get("name") else None),
                    "given": (p.get("name", [{}])[0].get("given", [None])[0] if p.get("name") else None),
                }
            )
        return out
