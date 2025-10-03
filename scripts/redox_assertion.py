# scripts/redox_assertion.py
# Usage:
#   python scripts/redox_assertion.py --assertion     # prints client_assertion JWT
#   python scripts/redox_assertion.py --token         # exchanges for access_token (prints token)
#   python scripts/redox_assertion.py --both          # prints both (assertion then token)
#   python scripts/redox_assertion.py --send-patient  # sends a PatientAdmin NewPatient message
#
# Reads JWK from env REDOX_PRIVATE_JWK, else from secrets/private_jwk.json
# Reads CLIENT_ID from env REDOX_CLIENT_ID, else constant
# Reads TOKEN_URL from env REDOX_TOKEN_URL, else default US URL
# Reads ENDPOINT_URL from env REDOX_ENDPOINT_URL, else default

import argparse
import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import jwt
import requests  # type: ignore[import-untyped]
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.ec import SECP384R1, EllipticCurvePrivateNumbers
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateNumbers
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["REDOX_CLIENT_ID"]
TOKEN_URL = os.environ["REDOX_TOKEN_URL"]  # e.g., https://auth.redoxengine.com/oauth/token
JWK_JSON = os.environ["REDOX_PRIVATE_JWK"]  # includes kty, n, e, d, kid, etc.


# ---------- helpers ----------
def b64u_dec(s: str) -> bytes:
    s_bytes = s.encode() if isinstance(s, str) else s
    pad = b"=" * (-len(s_bytes) % 4)
    return base64.urlsafe_b64decode(s_bytes + pad)


def load_jwk() -> Dict:
    env_val = JWK_JSON
    if env_val:
        return json.loads(env_val)
    # fallback to file
    path = os.path.join(os.getcwd(), "secrets", "private_jwk.json")
    if not os.path.exists(path):
        print("Error: REDOX_PRIVATE_JWK not set and secrets/private_jwk.json not found.", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def jwk_to_private_key(jwk: Dict):
    kty = jwk.get("kty")
    if kty == "RSA":
        required = ["n", "e", "d", "p", "q", "dp", "dq", "qi"]
        if any(x not in jwk for x in required):
            raise ValueError("RSA JWK missing CRT params (need n,e,d,p,q,dp,dq,qi). Regenerate keys to include them.")
        n = int.from_bytes(b64u_dec(jwk["n"]), "big")
        e = int.from_bytes(b64u_dec(jwk["e"]), "big")
        d = int.from_bytes(b64u_dec(jwk["d"]), "big")
        p = int.from_bytes(b64u_dec(jwk["p"]), "big")
        q = int.from_bytes(b64u_dec(jwk["q"]), "big")
        dp = int.from_bytes(b64u_dec(jwk["dp"]), "big")
        dq = int.from_bytes(b64u_dec(jwk["dq"]), "big")
        qi = int.from_bytes(b64u_dec(jwk["qi"]), "big")
        priv_numbers = RSAPrivateNumbers(
            p=p,
            q=q,
            d=d,
            dmp1=dp,
            dmq1=dq,
            iqmp=qi,
            public_numbers=rsa.RSAPublicNumbers(e=e, n=n),
        )
        return priv_numbers.private_key(default_backend()), "RS384"
    elif kty == "EC":
        crv = jwk.get("crv")
        if crv != "P-384":
            raise ValueError(f"Unsupported EC curve: {crv}. Expected P-384.")
        d = int.from_bytes(b64u_dec(jwk["d"]), "big")
        x = int.from_bytes(b64u_dec(jwk["x"]), "big")
        y = int.from_bytes(b64u_dec(jwk["y"]), "big")
        curve = SECP384R1()
        public_numbers = ec.EllipticCurvePublicNumbers(x, y, curve)
        private_numbers = EllipticCurvePrivateNumbers(d, public_numbers)
        return private_numbers.private_key(default_backend()), "ES384"
    else:
        raise ValueError(f"Unsupported kty: {kty}")


def build_client_assertion(private_key, kid: str, client_id: str, token_url: str, alg: str) -> str:
    now = int(time.time())
    claims = {
        "iss": client_id,
        "sub": client_id,
        "aud": token_url,
        "iat": now,
        "exp": now + 300,
        "jti": str(uuid.uuid4()),
    }
    headers = {"kid": kid} if kid else {}
    return jwt.encode(claims, private_key, algorithm=alg, headers=headers)


def get_access_token(token_url: str, assertion: str) -> str:
    resp = requests.post(
        token_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        },
        timeout=20,
    )
    try:
        data = resp.json()
    except Exception:
        print(resp.text, file=sys.stderr)
        resp.raise_for_status()
    if resp.status_code != 200:
        raise RuntimeError(f"Token error {resp.status_code}: {data}")
    return data["access_token"]


def send_patient_message(token: str) -> Dict[str, Any]:
    """Send a PatientAdmin NewPatient message to Redox API"""
    endpoint_url = os.getenv("REDOX_ENDPOINT_URL", "https://evening-earth.redoxengine.com/endpoint/message")

    # Create the message payload
    payload = {
        "Meta": {
            "DataModel": "PatientAdmin",
            "EventType": "NewPatient",
            "EventDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Test": True,
            "Destinations": [{"ID": "1e4bb53b-234a-4ca2-b206-14c36ca4efa7", "Name": "Mock EHR"}],
        },
        "Patient": {
            "Identifiers": [{"ID": "MRN123456", "IDType": "MRN"}],
            "Demographics": {
                "FirstName": "Jane",
                "LastName": "Doe",
                "DOB": "1984-07-13",
                "Sex": "F",
                "Address": {"StreetAddress": "123 Main St", "City": "Madison", "State": "WI", "ZIP": "53703"},
            },
        },
        "Visit": {
            "VisitNumber": "A01-20251002-001",
            "AttendingProvider": {"ID": "12345", "IDType": "NPI", "FirstName": "Alex", "LastName": "Smith"},
            "Location": {"Facility": "Main Hospital", "Department": "ED", "Room": "12A"},
        },
    }

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    resp = requests.post(endpoint_url, headers=headers, json=payload, timeout=30)

    if resp.status_code in [200, 201]:
        # Some endpoints return plain text success messages
        try:
            data = resp.json()
        except Exception:
            # If not JSON, return a success dict with the text response
            data = {"status": "success", "message": resp.text}
    else:
        try:
            data = resp.json()
        except Exception:
            print(f"Response status: {resp.status_code}", file=sys.stderr)
            print(f"Response text: {resp.text}", file=sys.stderr)
            resp.raise_for_status()

        raise RuntimeError(f"API error {resp.status_code}: {data}")

    return data


# ---------- main ----------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assertion", action="store_true", help="print the client_assertion JWT")
    parser.add_argument("--token", action="store_true", help="exchange assertion for access token")
    parser.add_argument("--both", action="store_true", help="print assertion then access token")
    parser.add_argument("--send-patient", action="store_true", help="send a PatientAdmin NewPatient message")
    args = parser.parse_args()

    jwk = load_jwk()
    kid = jwk.get("kid", "")
    client_id = os.getenv("REDOX_CLIENT_ID", CLIENT_ID)
    token_url = os.getenv("REDOX_TOKEN_URL", TOKEN_URL)

    key, alg = jwk_to_private_key(jwk)
    assertion = build_client_assertion(key, kid, client_id, token_url, alg)

    if args.assertion:
        print(assertion)
    elif args.token:
        token = get_access_token(token_url, assertion)
        print(token)
    elif args.both:
        print("ASSERTION:")
        print(assertion)
        print("\nACCESS_TOKEN:")
        print(get_access_token(token_url, assertion))
    elif args.send_patient:
        token = get_access_token(token_url, assertion)
        result = send_patient_message(token)
        print("Patient message sent successfully:")
        print(json.dumps(result, indent=2))
    else:
        # default: just print token
        print(get_access_token(token_url, assertion))
