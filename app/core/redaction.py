import re


def redact_text(s: str) -> str:
    # Remove emails, phones, SSN-like, keep dates/zip masked in logs
    s = re.sub(r"[\w\.-]+@[\w\.-]+", "[EMAIL]", s)
    s = re.sub(r"\b\d{3}[-.\s]?\d{2,3}[-.\s]?\d{4}\b", "[PHONE]", s)
    s = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", s)
    return s
