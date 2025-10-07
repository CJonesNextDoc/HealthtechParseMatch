# app/clients/deepgram_client.py
import os

import httpx

DG_API_KEY = os.environ["DEEPGRAM_API_KEY"]
DG_URL = "https://api.deepgram.com/v1/listen"


async def deepgram_transcribe_nbest(wav_bytes: bytes, *, alternatives: int = 5, numerals: bool = True) -> list[str]:
    headers = {"Authorization": f"Token {DG_API_KEY}"}
    params = {
        "alternatives": str(alternatives),
        "numerals": "true" if numerals else "false",
        # optional: "model": "phonecall", "tier": "enhanced", "punctuate": "true"
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(DG_URL, headers=headers, params=params, content=wav_bytes)
        r.raise_for_status()
        data = r.json()

    # Flatten alternatives (one-channel telephony assumed)
    out = []
    for ch in data.get("results", {}).get("channels", []):
        for alt in ch.get("alternatives", []):
            txt = (alt.get("transcript") or "").strip()
            if txt:
                out.append(txt)
    # Dedup preserve order
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:alternatives]
