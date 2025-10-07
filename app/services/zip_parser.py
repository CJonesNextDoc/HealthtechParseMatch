# app/services/zip_parser.py
import re
from typing import List, Tuple

_DIGIT_WORD = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "to": "2",
    "too": "2",
    "three": "3",
    "four": "4",
    "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "ate": "8",
    "nine": "9",
}
_PUNCT = str.maketrans({",": " ", ".": " ", "/": " "})


def _normalize(s: str) -> str:
    s = s.lower().translate(_PUNCT)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _words_to_digits_tokens(tokens: List[str]) -> List[str]:
    out: List[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "double" and i + 1 < len(tokens) and tokens[i + 1] in _DIGIT_WORD:
            out.append(_DIGIT_WORD[tokens[i + 1]] * 2)  # "double five" -> "55"
            i += 2
            continue
        out.append(_DIGIT_WORD.get(t, t))
        i += 1
    return out


def extract_zip5_candidates(text: str, *, allow_plus4: bool = False) -> List[Tuple[str, float]]:
    """
    Returns [(zip5, score)], sorted by score desc. If allow_plus4=True and a 9-digit ZIP is found,
    we still return the first 5 as the candidate, with a slight score bump.
    """
    t = _normalize(text)
    cand_scores: dict[str, float] = {}

    # 1) direct numeric 5 (and optional 4) detection
    for m in re.finditer(r"\b(\d{5})(?:-(\d{4}))?\b", t):
        zip5 = m.group(1)
        plus4 = m.group(2)
        score = 0.95 + (0.02 if (plus4 and allow_plus4) else 0.0)
        cand_scores[zip5] = max(cand_scores.get(zip5, 0), score)

    # 2) spelled digits → collapse to numeric stream, then find 5-digit sequences
    tokens = t.split()
    tokens = _words_to_digits_tokens(tokens)
    collapsed = "".join(ch for ch in " ".join(tokens) if ch.isdigit())
    for m in re.finditer(r"(?<!\d)(\d{5})(?!\d)", collapsed):
        zip5 = m.group(1)
        # Slightly lower than direct numeric to prefer exact transcripts
        cand_scores[zip5] = max(cand_scores.get(zip5, 0), 0.88)

    # 3) small context boost if the word “zip” shows up near digits/words
    if " zip " in f" {t} ":
        for z in list(cand_scores.keys()):
            cand_scores[z] = min(cand_scores[z] + 0.02, 0.99)

    # sort high→low
    return sorted(cand_scores.items(), key=lambda kv: -kv[1])
