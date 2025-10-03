"""
Redox API Client

Provides OAuth 2.0 client credentials authentication and API calls for Redox Engine.
Handles JWT assertion generation, token caching, and automatic refresh.
All methods are async to work properly with FastAPI and other async contexts.
"""

import asyncio
import hashlib
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, cast

import httpx
import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.ec import SECP384R1, EllipticCurvePrivateNumbers
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateNumbers


class RedoxClient:
    """
    Redox API client with automatic token management.

    Handles JWT assertion generation and access token caching/refresh.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        private_jwk: Optional[Dict] = None,
        token_url: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        token_cache_duration: int = 300,  # 5 minutes
    ):
        """
        Initialize Redox client.

        Args:
            client_id: Redox client ID (reads from REDOX_CLIENT_ID env var if not provided)
            private_jwk: Private JWK dict (reads from REDOX_PRIVATE_JWK env var if not provided)
            token_url: OAuth token endpoint (reads from REDOX_TOKEN_URL env var if not provided)
            endpoint_url: API endpoint URL (reads from REDOX_ENDPOINT_URL env var if not provided)
            token_cache_duration: How long to cache tokens in seconds (default: 300)
        """
        client_id_env = os.environ.get("REDOX_CLIENT_ID")
        if not client_id_env:
            raise ValueError("REDOX_CLIENT_ID environment variable must be set")
        self.client_id: str = client_id or client_id_env
        self.token_url: str = cast(
            str, token_url or os.environ.get("REDOX_TOKEN_URL", "https://auth.redoxengine.com/oauth/token")
        )
        self.endpoint_url: str = cast(
            str, endpoint_url or os.environ.get("REDOX_ENDPOINT_URL", "https://api.redoxengine.com/v2/endpoint")
        )

        # Load JWK
        if private_jwk:
            self.jwk = private_jwk
        else:
            self.jwk = self._load_jwk()

        self.token_cache_duration = token_cache_duration
        self._cached_token: Optional[Dict[str, Any]] = None
        self._token_expires_at: Optional[float] = None

    def _load_jwk(self) -> Dict:
        """Load JWK from environment variable or file."""
        env_val = os.environ.get("REDOX_PRIVATE_JWK")
        if env_val:
            return json.loads(env_val)
        # fallback to file
        path = os.path.join(os.getcwd(), "secrets", "private_jwk.json")
        if not os.path.exists(path):
            raise ValueError("REDOX_PRIVATE_JWK not set and secrets/private_jwk.json not found")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _is_token_valid(self) -> bool:
        """Check if cached token is still valid."""
        if not self._cached_token or not self._token_expires_at:
            return False
        # Add 30 second buffer to avoid edge cases
        return time.time() < (self._token_expires_at - 30)

    def _generate_assertion(self) -> str:
        """Generate JWT client assertion."""
        now = int(time.time())
        claims = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": self.token_url,
            "iat": now,
            "exp": now + 300,  # 5 minutes
            "jti": str(uuid.uuid4()),
        }

        headers = {"kid": self.jwk.get("kid")} if "kid" in self.jwk else {}

        key, alg = self._jwk_to_private_key(self.jwk)
        return jwt.encode(payload=claims, key=key, algorithm=alg, headers=headers)

    async def _get_access_token(self) -> str:
        """Exchange JWT assertion for access token."""
        assertion = self._generate_assertion()

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                self.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": assertion,
                },
            )

        if resp.status_code != 200:
            try:
                error_data = resp.json()
            except Exception:
                error_data = {"error": "unknown", "message": resp.text}
            raise RuntimeError(f"Token request failed {resp.status_code}: {error_data}")

        token_data = resp.json()
        self._cached_token = token_data
        # Cache for token's expires_in duration or default cache duration
        expires_in = token_data.get("expires_in", self.token_cache_duration)
        self._token_expires_at = time.time() + expires_in

        return token_data["access_token"]

    async def _post_with_retries(
        self,
        url: str,
        headers: dict[str, str],
        json_payload: dict,
        *,
        max_attempts: int = 5,
        base_delay: float = 0.5,
        timeout: float = 30.0,
    ) -> httpx.Response:
        """
        Async POST with exponential backoff and idempotency.
        - Adds Idempotency-Key (SHA-256 of sorted JSON) if not already present.
        - Retries on 429, 500, 502, 503, 504 (uses Retry-After if provided).
        """
        # Stable idempotency key for this payload
        if "Idempotency-Key" not in headers:
            idem_key = hashlib.sha256(json.dumps(json_payload, sort_keys=True).encode("utf-8")).hexdigest()
            headers = {**headers, "Idempotency-Key": idem_key}

        attempt = 0
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            while attempt < max_attempts:
                attempt += 1
                try:
                    resp = await client.post(url, headers=headers, json=json_payload)

                    # transient server/rate-limit errors -> backoff
                    if resp.status_code in (429, 500, 502, 503, 504):
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = base_delay * (2 ** (attempt - 1))
                        else:
                            delay = base_delay * (2 ** (attempt - 1))
                        # add jitter
                        delay += random.uniform(0, delay * 0.25)
                        await asyncio.sleep(delay)
                        continue

                    return resp

                except httpx.RequestError as exc:
                    # network/transport errors -> retry with backoff
                    last_exc = exc
                    if attempt >= max_attempts:
                        break
                    delay = base_delay * (2 ** (attempt - 1))
                    delay += random.uniform(0, delay * 0.25)
                    await asyncio.sleep(delay)

        if last_exc:
            raise RuntimeError(f"POST {url} failed after {max_attempts} attempts: {last_exc}") from last_exc
        raise RuntimeError(f"POST {url} failed after {max_attempts} attempts (no response).")

    async def get_token(self) -> str:
        """
        Get a valid access token, using cache if available.

        Returns:
            Access token string
        """
        if self._is_token_valid():
            assert self._cached_token is not None  # mypy guard
            return self._cached_token["access_token"]

        return await self._get_access_token()

    async def send_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message to Redox API endpoint with retries and idempotency.

        Args:
            payload: Message payload dict

        Returns:
            API response dict
        """
        token = await self.get_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        resp = await self._post_with_retries(
            f"{self.endpoint_url}/message",
            headers=headers,
            json_payload=payload,
            max_attempts=5,
            base_delay=1.0,  # Start with 1 second base delay
            timeout=30.0,
        )

        if resp.status_code in [200, 201]:
            try:
                return resp.json()
            except Exception:
                return {"status": "success", "message": resp.text}
        else:
            try:
                error_data = resp.json()
            except Exception:
                error_data = {"error": "unknown", "message": resp.text}
            raise RuntimeError(f"API request failed {resp.status_code}: {error_data}")

    async def send_patient_admin_message(
        self, patient_data: Dict[str, Any], event_type: str = "NewPatient"
    ) -> Dict[str, Any]:
        """
        Send a PatientAdmin message.

        Args:
            patient_data: Patient data dict
            event_type: Event type (default: "NewPatient")

        Returns:
            API response dict
        """
        payload = {
            "Meta": {
                "DataModel": "PatientAdmin",
                "EventType": event_type,
                "EventDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "Test": True,
                "Destinations": [{"ID": "1e4bb53b-234a-4ca2-b206-14c36ca4efa7", "Name": "Mock EHR"}],
            },
            **patient_data,
        }

        return await self.send_message(payload)

    # ---------- Helper methods (copied from original script) ----------

    def _b64u_dec(self, s: str) -> bytes:
        s_bytes = s.encode() if isinstance(s, str) else s
        pad = b"=" * (-len(s_bytes) % 4)
        return jwt.utils.base64url_decode(s_bytes + pad)

    def _jwk_to_private_key(self, jwk: Dict):
        """Convert JWK to cryptography private key."""
        kty = jwk.get("kty")
        if kty == "RSA":
            required = ["n", "e", "d", "p", "q", "dp", "dq", "qi"]
            if any(x not in jwk for x in required):
                raise ValueError("RSA JWK missing CRT params (need n,e,d,p,q,dp,dq,qi). Regenerate keys to include them.")

            n = int.from_bytes(self._b64u_dec(jwk["n"]), "big")
            e = int.from_bytes(self._b64u_dec(jwk["e"]), "big")
            d = int.from_bytes(self._b64u_dec(jwk["d"]), "big")
            p = int.from_bytes(self._b64u_dec(jwk["p"]), "big")
            q = int.from_bytes(self._b64u_dec(jwk["q"]), "big")
            dp = int.from_bytes(self._b64u_dec(jwk["dp"]), "big")
            dq = int.from_bytes(self._b64u_dec(jwk["dq"]), "big")
            qi = int.from_bytes(self._b64u_dec(jwk["qi"]), "big")

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

            d = int.from_bytes(self._b64u_dec(jwk["d"]), "big")
            x = int.from_bytes(self._b64u_dec(jwk["x"]), "big")
            y = int.from_bytes(self._b64u_dec(jwk["y"]), "big")

            curve = SECP384R1()
            public_numbers = ec.EllipticCurvePublicNumbers(x, y, curve)
            private_numbers = EllipticCurvePrivateNumbers(d, public_numbers)
            return private_numbers.private_key(default_backend()), "ES384"

        else:
            raise ValueError(f"Unsupported kty: {kty}")


# Convenience functions for backward compatibility
def get_redox_client() -> RedoxClient:
    """Get a configured Redox client instance."""
    return RedoxClient()


async def get_access_token() -> str:
    """Get a fresh access token (convenience function)."""
    client = get_redox_client()
    return await client.get_token()
