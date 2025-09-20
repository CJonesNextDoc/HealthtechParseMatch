import re
from datetime import date, datetime

from app.utils.logger import get_logger
from app.utils.logging_config import setup_logging

# Configure logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


# from .parser_primitives import MONTHS, ORDINAL_WORD, normalize_spaces, pick_year_from_two_digits, words_to_digits_seq
_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

# Ordinal‐word → digit (supports both hyphenated & spaced forms)
_ORDINAL = {
    "first": "1",
    "one": "1",
    "second": "2",
    "two": "2",
    "third": "3",
    "three": "3",
    "fourth": "4",
    "four": "4",
    "fifth": "5",
    "five": "5",
    "sixth": "6",
    "six": "6",
    "seventh": "7",
    "seven": "7",
    "eighth": "8",
    "eight": "8",
    "ninth": "9",
    "nine": "9",
    "tenth": "10",
    "ten": "10",
    "eleventh": "11",
    "eleven": "11",
    "twelfth": "12",
    "twelve": "12",
    "thirteenth": "13",
    "thirteen": "13",
    "fourteenth": "14",
    "fourteen": "14",
    "fifteenth": "15",
    "fifteen": "15",
    "sixteenth": "16",
    "sixteen": "16",
    "seventeenth": "17",
    "seventeen": "17",
    "eighteenth": "18",
    "eighteen": "18",
    "nineteenth": "19",
    "nineteen": "19",
    "twentieth": "20",
    "twenty": "20",
    "twenty first": "21",
    "twenty-first": "21",
    "twenty one": "21",
    "twenty-one": "21",
    "twenty second": "22",
    "twenty-second": "22",
    "twenty two": "22",
    "twenty-two": "22",
    "twenty third": "23",
    "twenty-third": "23",
    "twenty three": "23",
    "twenty-three": "23",
    "twenty fourth": "24",
    "twenty-fourth": "24",
    "twenty four": "24",
    "twenty-four": "24",
    "twenty fifth": "25",
    "twenty-fifth": "25",
    "twenty five": "25",
    "twenty-five": "25",
    "twenty sixth": "26",
    "twenty-sixth": "26",
    "twenty six": "26",
    "twenty-six": "26",
    "twenty seventh": "27",
    "twenty-seventh": "27",
    "twenty seven": "27",
    "twenty-seven": "27",
    "twenty eighth": "28",
    "twenty-eighth": "28",
    "twenty eight": "28",
    "twenty-eight": "28",
    "twenty ninth": "29",
    "twenty-ninth": "29",
    "twenty nine": "29",
    "twenty-nine": "29",
    "thirtieth": "30",
    "thirty": "30",
    "thirty first": "31",
    "thirty-first": "31",
    "thirty one": "31",
    "thirty-one": "31",
}


# Words → numeric for parsing spelled‐out years
_WORD_NUM = {
    **{
        w: n
        for w, n in zip(
            [
                "ten",
                "eleven",
                "twelve",
                "thirteen",
                "fourteen",
                "fifteen",
                "sixteen",
                "seventeen",
                "eighteen",
                "nineteen",
            ],
            range(10, 20),
        )
    },
    **{
        w: n * 10
        for w, n in zip(
            [
                "twenty",
                "thirty",
                "forty",
                "fifty",
                "sixty",
                "seventy",
                "eighty",
                "ninety",
            ],
            range(2, 10),
        )
    },
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}


def try_dtmf_dob(text: str, *, today: date | None = None, min_age: int = 0, max_age: int = 120):
    # Handle pure numeric MMDDYYYY or MMDDYY with no spaces or delimiters
    # Collapse any whitespace between numbers, trim
    text_to_parse = re.sub(r"\s+", "", text)
    text_to_parse = text_to_parse.lower().strip().replace(" ", "")
    logger.debug(f"Text to parse: {text_to_parse}")
    # Check to see if it is all digits and length is 6 or 8. This could be a touch-tone DTMF input
    if text_to_parse.isdigit() and len(text_to_parse) in (8, 6):
        text_to_check = f"{text_to_parse[:2]}-{text_to_parse[2:4]}-{text_to_parse[4:]}"
        logger.debug(f"Text to check: {text_to_check}")
        try:
            parsed_dt = datetime.strptime(text_to_check, "%m-%d-%Y" if len(text_to_parse) == 8 else "%m-%d-%y").date()
            logger.debug(f"Parsed date: {parsed_dt}")
            if today is None:
                today = date.today()
            age = today.year - parsed_dt.year - ((today.month, today.day) < (parsed_dt.month, parsed_dt.day))
            parsed_year = parsed_dt.year
            logger.debug(f"Age: {age}")
            if age > max_age:
                parsed_year = parsed_dt.year + 100
                age = today.year - parsed_year - ((today.month, today.day) < (parsed_dt.month, parsed_dt.day))
            if age < 0:
                parsed_year = parsed_dt.year - 100
                age = today.year - parsed_year - ((today.month, today.day) < (parsed_dt.month, parsed_dt.day))
                logger.debug(f"Adjusted Age: {age}")
            if min_age <= age <= max_age:
                date_parts = {"year": parsed_year, "month": parsed_dt.month, "day": parsed_dt.day}
                logger.debug(f"Returning date parts: {date_parts}")
                return date_parts
                # return [(iso, 1.0)]
        except ValueError:
            pass

    return None


def parse_dob_candidates(text: str, *, today: date | None = None, min_age: int = 0, max_age: int = 120) -> dict[str, list]:
    """Return [(iso, score)] sorted desc."""
    dtmf_dob = try_dtmf_dob(text, today=today, min_age=min_age, max_age=max_age)
    logger.debug(f"Date to parse: {text}")
    if dtmf_dob:
        rtn_msg = {
            "iso": f"{dtmf_dob['year']}-{dtmf_dob['month']:02d}-{dtmf_dob['day']:02d}",
            "year": dtmf_dob["year"],
            "month": dtmf_dob["month"],
            "day": dtmf_dob["day"],
            "score": 0.99,
        }
        logger.debug(f"DTMF parsed date: {rtn_msg}")
        rtn = {"dob_candidates": [rtn_msg]} if rtn_msg else {"dob_candidates": []}
        return rtn

    parsed_dt = parse_spoken_date(text)
    parsed_dt["score"] = 0.8 if parsed_dt else 0.0
    parsed_dt["iso"] = f"{parsed_dt['year']}-{parsed_dt['month']:02d}-{parsed_dt['day']:02d}" if parsed_dt else ""
    logger.debug(f"Parsed date: {parsed_dt}")
    rtn = {"dob_candidates": [parsed_dt]} if parsed_dt else {"dob_candidates": []}
    return rtn


def _expand_two_digit_year(yy: int) -> int:
    """
    Map 00-99 → 1900-1999 or 2000-2099.

    • Anything *ahead* of the current year's last-two-digits is assumed 1900-1999.
      e.g. 56 → 1956 if today is 2025.
    • Anything ≤ current YY is assumed 2000-2099.
      e.g. 05 → 2005 if today is 2025.

    Adjust the heuristic if your domain has different needs.
    """
    now_yy = datetime.now().year % 100
    century = 2000 if yy <= now_yy else 1900
    return century + yy


def _parse_year(words: str) -> int | None:
    txt = words.lower().replace("-", " ").strip()
    now_year = datetime.now().year

    # — handle “two thousand and three” —
    if "thousand" in txt:
        toks = txt.split()
        try:
            idx = toks.index("thousand")
            # parse the thousands part
            thousands = sum(_WORD_NUM.get(tok, 0) for tok in toks[:idx])
            # parse the remainder (skip "and")
            rem = sum(_WORD_NUM.get(tok, 0) for tok in toks[idx + 1 :] if tok != "and")
            year = thousands * 1000 + rem
            if 1000 <= year <= now_year:
                return year
        except ValueError:
            pass

    # — pure 4-digit numeric —
    if re.fullmatch(r"\d{4}", txt):
        yr = int(txt)
        return yr if 1900 <= yr <= now_year else None

    # — pure 2-digit numeric —
    if re.fullmatch(r"\d{2}", txt):
        return _expand_two_digit_year(int(txt))

    toks = txt.split()
    logger.debug(f"yrtoks: {toks}")
    if len(toks) == 1 and all(tok in _WORD_NUM for tok in toks):
        prefix = _WORD_NUM.get(toks[0], 0)
        return _expand_two_digit_year(prefix)

    elif len(toks) == 2 and all(tok in _WORD_NUM for tok in toks):
        prefix = _WORD_NUM.get(toks[0], 0)
        suffix = _WORD_NUM.get(toks[1], 0)
        logger.debug(f"prefix: {prefix}")
        logger.debug(f"suffix: {suffix}")

        if prefix == 19 and suffix > 9:
            # concatenate don't sum
            logger.debug(f"prefix: {prefix}")
            logger.debug(f"suffix: {suffix}")
            yr = int(str(prefix) + str(suffix))
            logger.debug(f"yr: {yr}")
            if yr < 2000:
                return yr
        elif prefix == 20 and suffix > 9 and suffix <= (now_year - 2000):
            yr = int(2000 + suffix)
            logger.debug(f"yr: {yr}")
            if yr >= 2000:
                return yr
        elif prefix == 20 and suffix <= 9:
            yr = prefix + suffix
            logger.debug(f"new yr: {yr}")
            return _expand_two_digit_year(yr)
        elif prefix < 10 and suffix < 10:
            yr = int(str(prefix) + str(suffix))
            return _expand_two_digit_year(yr)
        else:
            yr = prefix + suffix
            if 0 <= yr <= 99:
                return _expand_two_digit_year(yr)

    # — 2-word cardinal: handle centuries correctly —
    if len(toks) == 2 and all(tok in _WORD_NUM for tok in toks):
        prefix = _WORD_NUM[toks[0]]
        suffix = _WORD_NUM[toks[1]]
        # a) if prefix >= 10, treat as century (e.g. "twenty fifteen" → 2015)
        # if prefix >= 10:
        #     yr = prefix * 100 + suffix
        #     if 1000 <= yr <= now_year:
        #         return yr
        if prefix >= 10:
            yr = prefix + suffix
            if 0 <= yr <= 99:
                return _expand_two_digit_year(yr)

        # b) otherwise fallback to two-digit year (e.g. "nineteen five" → 19+5)
        yy = prefix + suffix
        if 0 <= yy <= 99:
            return _expand_two_digit_year(yy)

    # CSJ Catching a weird tongue twister answer
    if len(toks) == 3 and toks[0] == "nineteenth" and _WORD_NUM.get(toks[0]) is None:
        toks[0] = "nineteen"
    if len(toks) == 3 and toks[0] == "twentieth" and _WORD_NUM.get(toks[0]) is None:
        toks[0] = "twenty"

    # CSJ Added this if and moved former if down as elif below
    # 4 tokens (e.g. "one nine five six") —
    logger.debug(toks)
    if len(toks) == 4 and _WORD_NUM.get(toks[0]) is not None:
        wn0 = None
        wn1 = None
        wn2 = None
        wn3 = None
        try:
            wn0 = _WORD_NUM[toks[0]]
            wn1 = _WORD_NUM[toks[1]]
            wn2 = _WORD_NUM[toks[2]]
            wn3 = _WORD_NUM[toks[3]]
            yr_txt = str(wn0) + str(wn1) + str(wn2) + str(wn3)
            yr = int(yr_txt)
        except Exception as ex:
            if toks:
                logger.error(f"Exception: {ex} in _parse_year, trying to extract year from toks: {toks}")
            else:
                logger.error(f"Exception: {ex} in _parse_year, trying to extract year from toks, but no value for toks.")

        if 1900 <= yr <= now_year:
            return yr

    elif len(toks) >= 2 and _WORD_NUM.get(toks[0]) is not None:
        prefix = _WORD_NUM[toks[0]]
        logger.debug(f"prefix: {prefix}")
        # Leaving this here because it is only place I need it right now.
        _WORD_NUM_SINGLE = {
            "zero": 0,
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
        }

        # Inserted to handle concatenations
        if all(tok in _WORD_NUM_SINGLE for tok in toks[1:]):
            # concatenate numeric tokens: "six six" → "66"
            suffix_str = "".join(str(_WORD_NUM_SINGLE[tok]) for tok in toks[1:])
            logger.debug(f"suffix_str: {suffix_str}")
            suffix = int(suffix_str)
        else:
            # fallback to sum if any token isn't clean
            suffix = sum(_WORD_NUM.get(tok, 0) for tok in toks[1:])
            logger.debug(f"suffix: {suffix}")

        yr = prefix * 100 + suffix
        if 1000 <= yr <= now_year:
            return yr
        elif 900 <= yr <= 999:
            # somehow 19 was interpreted as nine
            return yr + 1000

    return None


# ── Main Parser ────────────────────────────────────────────────────────────────
def parse_spoken_date(text: str, attempt: int = 1) -> dict:
    """
    CSJ - Modified this function in a couple of places
    """
    parts: dict[str, int] = {}

    # If there are *any* digits in text, convert to word
    if bool(re.search(r"\d", text)):
        DIGIT_TO_WORD = {
            "0": "zero",
            "1": "one",
            "2": "two",
            "3": "three",
            "4": "four",
            "5": "five",
            "6": "six",
            "7": "seven",
            "8": "eight",
            "9": "nine",
        }
        digit_word = "".join(DIGIT_TO_WORD[d] + " " if d in DIGIT_TO_WORD else d for d in text)

        logger.debug(f"text in: {text}")
        logger.debug(f"All Digits to Word: {digit_word}")
        my_tokens = re.findall(r"\b[\w-]+\b", digit_word.lower())
        logger.debug(my_tokens)
    else:
        my_tokens = re.findall(r"\b[\w-]+\b", text.lower())

    # Consider any word superfluous that has no match in _WORD_NUM, _MONTHS, or _ORDINAL
    logger.debug(my_tokens)
    tokens = [word for word in my_tokens if word in _WORD_NUM or word in _MONTHS or word in _ORDINAL or word == "thousand"]

    logger.debug(tokens)
    if len(tokens) < 1:
        return parts

    # double-entered zero probably. Very narrow now, but we can expand as we see more
    if len(tokens) == 9 and tokens[0] == "zero" and tokens[1] == "zero":
        tokens.remove("zero")

    logger.debug(f"After remove extra zero, tokens: {tokens}")

    if tokens[0] in [
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
    ]:
        # This is most likely a month but it will probably be short and will need leading zero
        tokens.insert(0, "zero")
        # pass
        logger.debug(f"After insert zero, tokens: {tokens}")

    head = None
    # 0) No-month special: e.g. "one five fifty six" or "tenth nineteen fifty six"
    mon_idx = next((i for i, w in enumerate(tokens) if w in _MONTHS), None)
    if mon_idx is None:
        logger.debug(tokens)
        # 0a) numeric month/day/year, with support for two-word day only when tens
        if len(tokens) >= 3 and tokens[0] in _WORD_NUM and tokens[1] in _WORD_NUM:
            # Added a check for leading 'zero' as placeholder and a resulting offset
            if tokens[0] == "zero":
                m = _WORD_NUM[tokens[1]]
                offset = 1
            elif tokens[0] == "one" and tokens[1] == "zero":
                m = 10
                offset = 1
            elif tokens[0] == "one" and tokens[1] == "one":
                m = 11
                offset = 1
            elif tokens[0] == "one" and tokens[1] == "two":
                m = 12
                offset = 1
            elif tokens[1] == "zero" or tokens[1] == "one" or tokens[1] == "two":
                offset = 1
                m = int(str(_WORD_NUM[tokens[0]]) + str(_WORD_NUM[tokens[1]]))
            else:
                offset = 0
                m = _WORD_NUM[tokens[0]]

            logger.debug(f"m: {m}")
            logger.debug(f"offset: {offset}")

            if tokens[1 + offset] == "zero":
                offset += 1

            if offset >= 2:
                logger.debug(f"offset: {offset}")
                logger.debug(f"tokens: {tokens}")

            # two-word day only if tens ('twenty','thirty') + unit
            if (
                len(tokens) >= 4
                and len(tokens) > (2 + offset)
                and tokens[1 + offset] in ("twenty", "thirty")
                and tokens[2 + offset] in _WORD_NUM
            ):
                two_day = _WORD_NUM[tokens[1 + offset]] + _WORD_NUM[tokens[2 + offset]]
                logger.debug(f"two_day: {two_day}")
                if 1 <= two_day <= 31:
                    d = two_day
                    year_tokens = tokens[3 + offset :]
                else:
                    d = _WORD_NUM[tokens[1 + offset]]
                    year_tokens = tokens[2 + offset :]
            elif (
                len(tokens) >= 4
                and len(tokens) > (2 + offset)
                and tokens[1 + offset] in _WORD_NUM
                and tokens[2 + offset] in _WORD_NUM
            ):
                if tokens[0] == "zero" and tokens[1] == "one" and tokens[2] == "zero":
                    my_day = _WORD_NUM[tokens[3]]
                elif tokens[0] == "one" and tokens[1] == "zero" and tokens[2] == "zero":
                    my_day = _WORD_NUM[tokens[3]]
                elif tokens[0] == "one" and tokens[1] == "one" and tokens[2] == "zero":
                    my_day = _WORD_NUM[tokens[3]]
                elif tokens[0] == "one" and tokens[1] == "two" and tokens[2] == "zero":
                    my_day = _WORD_NUM[tokens[3]]
                else:
                    my_day = int(str(_WORD_NUM[tokens[1 + offset]]) + str(_WORD_NUM[tokens[2 + offset]]))
                logger.debug(f"my_day: {my_day}")
                if 10 <= my_day <= 31:
                    d = my_day
                    year_tokens = tokens[3 + offset :]
                    logger.debug(f"my_day: {d}")
                    logger.debug(f"year_tokens: {year_tokens}")
                else:
                    d = _WORD_NUM[tokens[1 + offset]]
                    year_tokens = tokens[2 + offset :]
                    logger.debug(f"my_day else: {d}")
                    logger.debug(f"year_tokens else: {year_tokens}")
            else:
                d = _WORD_NUM[tokens[1 + offset]]
                logger.debug(f"d: {d}")
                year_tokens = tokens[2 + offset :]

            if 1 <= m <= 12 and 1 <= d <= 31:
                parts["month"] = int(m)
                parts["day"] = int(d)
                y = _parse_year(" ".join(year_tokens))
                if y:
                    parts["year"] = y
                return parts

        # 0b) ordinal-day + spelled-out year
        day_offset = 0
        if len(tokens) >= 2 and f"{tokens[0]} {tokens[1]}" in _ORDINAL:
            parts["day"] = int(_ORDINAL[f"{tokens[0]} {tokens[1]}"])
            day_offset = 2
        elif tokens:
            w = tokens[0]
            if w in _ORDINAL:
                parts["day"] = int(_ORDINAL[w])
                day_offset = 1
            elif w in _WORD_NUM and 1 <= _WORD_NUM[w] <= 31:
                parts["day"] = _WORD_NUM[w]
                day_offset = 1
        tail = tokens[day_offset:]
        if tail:
            y = _parse_year(" ".join(tail))
            if y:
                parts["year"] = y
        return parts
    else:
        # See if there is a legit day before the mon_idx (e.g. twenty third April nineteen sixty three)
        if mon_idx == 1 and len(tokens) > 2:
            head = [tokens[0]]
        elif mon_idx == 2 and len(tokens) > 3:
            head = [tokens[0], tokens[1]]
    # 1) Month-present parsing
    parts["month"] = _MONTHS[tokens[mon_idx]]
    # 2) Pure-year gate
    tail = tokens[mon_idx + 1 :]

    if tail:
        allowed = set(_WORD_NUM) | {"and", "hundred", "thousand"}
        is_all_allowed = all(tok.isdigit() or tok in allowed for tok in tail)
        big_pos = next((i for i, tok in enumerate(tail) if tok in ("hundred", "thousand")), None)
        small_tail = len(tail) <= 3
        if is_all_allowed and (small_tail or big_pos == 1):
            y = _parse_year(" ".join(tail))
            if y:
                parts["year"] = y
                logger.debug(f"yr: {parts['year']}")
                logger.debug(f"return back with year {y}")
                # return parts

    # 3) Day parsing (1-2 token ordinal or cardinal)
    day_offset = 0
    # two-word ordinal (e.g. "twenty fourth")
    logger.debug(f"month: {parts['month'] }")

    logger.debug(f"mon_idx+2: {mon_idx+2}")
    if head is not None:
        # get the day from the head
        if len(head) > 1:
            two = f"{head[0]} {head[1]}"
            if two in _ORDINAL:
                parts["day"] = int(_ORDINAL[two])
        else:
            parts["day"] = int(_ORDINAL[head[0]])

    if mon_idx + 2 < len(tokens):
        two = f"{tokens[mon_idx+1]} {tokens[mon_idx+2]}"
        logger.debug(f"two: {two}")
        if two in _ORDINAL:
            parts["day"] = int(_ORDINAL[two])
            day_offset = 2
    # single token
    logger.debug("Checking day")
    if "day" not in parts and mon_idx + 1 < len(tokens):
        w = tokens[mon_idx + 1]
        if w in _ORDINAL:
            parts["day"] = int(_ORDINAL[w])
            day_offset = 1
        elif w in _WORD_NUM and 1 <= _WORD_NUM[w] <= 31:
            parts["day"] = _WORD_NUM[w]
            day_offset = 1
        else:
            m = re.search(r"\d+", w)  # type: ignore
            if m is not None:
                parts["day"] = int(m.group())  # type: ignore
                day_offset = 1
    logger.debug(f"Day: {parts['day']}")
    # 4) Year fallback
    tail2 = tokens[mon_idx + 1 + day_offset :]
    logger.debug(f"tail2: {tail2}")
    for tk in tail2:
        if re.fullmatch(r"(19|20)\d{2}", tk):
            parts["year"] = int(tk)
            break
    else:
        y = _parse_year(" ".join(tail2))
        if y:
            parts["year"] = y
            logger.debug(f"Year: {parts['year']}")
            logger.debug(" ".join(tail2))

    return parts
