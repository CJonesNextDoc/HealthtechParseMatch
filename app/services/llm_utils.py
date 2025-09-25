import re
from datetime import date, datetime

from jsonschema import validate


def redact_phi(s: str) -> str:
    s = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[EMAIL]", s)
    s = re.sub(r"\b\d{3}[-.\s]?\d{2,3}[-.\s]?\d{4}\b", "[PHONE]", s)
    return s


def within_age_window(iso: str, min_age=0, max_age=120, today: date | None = None) -> bool:
    today = today or date.today()
    try:
        d = datetime.strptime(iso, "%Y-%m-%d").date()
    except ValueError:
        return False
    age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    return min_age <= age <= max_age


def validate_json(payload: dict, schema: dict) -> dict:
    validate(instance=payload, schema=schema)
    return payload
