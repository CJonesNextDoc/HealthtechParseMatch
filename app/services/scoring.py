from dataclasses import dataclass


@dataclass
class MatchSignals:
    dob: bool
    zip_exact: bool
    zip_prefix: bool
    last4_match: bool
    last_name_prefix: bool
    first_initial: bool


# Transparent weights (tune in evals)
WEIGHTS = {
    "dob": 1.00,
    "zip_exact": 0.60,
    "zip_prefix": 0.20,
    "last4_match": 0.30,
    "last_name_prefix": 0.25,
    "first_initial": 0.10,
}


def score(signals: MatchSignals) -> float:
    s = 0.0
    for k, v in signals.__dict__.items():
        if v:
            s += WEIGHTS[k]
    return round(min(s, 1.0), 2)
