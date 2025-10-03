"""
Tests for Redox API client.

Tests JWT assertion generation, token caching, and API message sending.
"""

import json
import os
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.clients.redox_client import RedoxClient

# Skip all Redox tests if required environment variables are not set
redox_env_available = bool(os.environ.get("REDOX_CLIENT_ID"))


class TestRedoxClient:
    """Test suite for RedoxClient."""

    @pytest.fixture
    def sample_jwk(self):
        """Sample RSA JWK for testing."""
        return {
            "kty": "RSA",
            "n": "xgoz69pTDshgRTwZ4DMkWthIMZqoqwZQABq9xXJc0Fj25GLImUpVYmgsAQX2tZdR6z59MwcCBFnuvWIOS2uwaWATpB_i2WUrBEiQgcUS-CX4z9xcBSmM8dklqcIwC2q1F-cMdlUJquw0GFE4Gsr7iwxnn9MaucS6zIl7KlnCkVAouYj67R2TrJQ5cAfvpdud_b7Wrmix2Cez9m8DUhfY2TWujZv_H5JlRuh7J7wMmlZi3Os2XWyM3WYHFSTzkXG2O_oRTP51macwivXpqclZOh070mJV0OgT0qM0rOpD3B4sLTzcoGBMtpjUDJIbb8FZWXV7BKwtiYAdvjxADlB-2Q",  # noqa: E501
            "e": "AQAB",
            "d": "MnRK1Jururhsl-GuMpFWtMXQKrs0RUnDOUcApdK0IiF-CX2d7SFrj0eOnIl2gYt2CZ09wn59nIclxXVpiIGUz2znBMN8LtMRH5HFUEcTuu8oRWnExWFBrxKslZBdR6M85zoPU5non56LaAfi0W7z76T7jKlHcHrFK-4dYJfk9W-EUIErU_tCCYrj0ckE5b6k5nn2a7_9ke7JHQGMGLPgGe83uYZ_-TtFj739BKIzRRlKQ2GdNPais-2REqcq9BddArBeqzcKaJ7LkZOB94oMij7KkDpwdIDFt6Llj16j27Snl_CVkHGTVZDcYEytbIWRgBIqV4ZyTNUsnqYbcjYx",  # noqa: E501
            "p": "6EBp65SQO5ONrrujoQ2f5aPCkuRvEObuDBp5QSAhi3VNy-zL1rKHHu6IeaEC50FpqSd2wlyn6v1R2o57NEib5ex-3Bhf8_bwiPMopr1Edusgx0EFhK-O4jScR6sAUqIEqerfhHnLJhSHOLuBPA4NmmJUJHJZtYfoXzNxHd2DWwk",  # noqa: E501
            "q": "2ko8vRDnTzgJyn-1zblThP3rqdundU74KctxKtWSox_l39g-Jzaaq3aCzxTgE3EYAYKeo4DmHeBnsDPRq1HXJ3xryaJzOlyF2c4r9jInyLn3jO2aiOiimKfdW0BCFgNa3qA_gm8nCKq2Kkk_PV-tZ5J2E_H-XFpUK3rJU7SaaVE",  # noqa: E501
            "dp": "Sl_OS5WwtpNi7NDD7qBJUyWk-ptSgewh0RhtOhDLDTjMaAB1qlRTdvFWHPUV0-6booKzwjwfvd3PZ5j3FWAnJHMekObxW1P55TFRFExJ73cOcSB-XuZFcGT-oui82rltmuhPGcJS7ufmAaHyGcQ6UPUqEt3Xoo1aOZpkn_a-yNk",  # noqa: E501
            "dq": "azwa-HpMV5Nc4_i3FDgdunCPC-OXMT65FLcXggZnQfGSmNN_PP5LHz5Z5mcH6SUeuOc1DXduFHFAHsRmFPZgbsplnSlL1_jJ3IS2_fwHpUkOPlIfH3DBJ6MXUBOSI4REaKdqa6Y1E8HhOYbAJWNSKVY-4W95GF9bh_yK2K8ZR_E",  # noqa: E501
            "qi": "JN7RsVLa0ol5X0_olDWw2-mCXuA52Bg5STZG48y8a9TWeLnILr9bS8PWS0leeep6kRWjIkvVo866EybJJlVsK_d6Y0Zq2qGy55tlQfsK5n2SNlWTvgyKQ6YJlRX-B7BnN_t3a6UQjACqpd2NLTAC90s4QzoD9IPDiaahpmyFSFc",  # noqa: E501
            "kid": "test-key-id",
            "alg": "RS384",
        }

    @pytest.fixture
    def client(self, sample_jwk):
        """Create a RedoxClient instance for testing."""
        return RedoxClient(
            client_id="test-client-id",
            private_jwk=sample_jwk,
            token_url="https://test.auth.example.com/token",
            endpoint_url="https://test.api.example.com",
            token_cache_duration=300,
        )

    @pytest.mark.skipif(not redox_env_available, reason="REDOX_CLIENT_ID environment variable not set")
    def test_client_initialization(self, client):
        """Test that client initializes with correct parameters."""
        assert client.client_id == "test-client-id"
        assert client.token_url == "https://test.auth.example.com/token"
        assert client.endpoint_url == "https://test.api.example.com"
        assert client.token_cache_duration == 300
        assert client._cached_token is None
        assert client._token_expires_at is None

    @pytest.mark.skipif(not redox_env_available, reason="REDOX_CLIENT_ID environment variable not set")
    def test_generate_assertion(self, client):
        """Test JWT assertion generation."""
        assertion = client._generate_assertion()

        # Should be a JWT string with 3 parts separated by dots
        parts = assertion.split(".")
        assert len(parts) == 3

        # Decode header to verify kid
        import base64

        header = json.loads(base64.urlsafe_b64decode(parts[0] + "==").decode())
        assert header["kid"] == "test-key-id"
        assert header["alg"] == "RS384"

    @pytest.mark.skipif(not redox_env_available, reason="REDOX_CLIENT_ID environment variable not set")
    @pytest.mark.asyncio
    async def test_get_token_caching(self, client):
        """Test token caching and refresh logic."""
        # Mock the token response
        mock_response_data = {"access_token": "test-token-123", "token_type": "Bearer", "expires_in": 3600}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value=mock_response_data)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # First call should make HTTP request
            token1 = await client.get_token()
            assert token1 == "test-token-123"
            assert mock_client.post.call_count == 1

            # Second call should use cache
            token2 = await client.get_token()
            assert token2 == "test-token-123"
            assert mock_client.post.call_count == 1  # Still 1, used cache

    @pytest.mark.skipif(not redox_env_available, reason="REDOX_CLIENT_ID environment variable not set")
    @pytest.mark.asyncio
    async def test_token_expiration(self, client):
        """Test that expired tokens are refreshed."""
        # Set up expired token
        client._cached_token = {"access_token": "expired-token"}
        client._token_expires_at = time.time() - 100  # Expired 100 seconds ago

        # Mock new token response
        mock_response_data = {"access_token": "fresh-token-456", "token_type": "Bearer", "expires_in": 3600}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value=mock_response_data)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Should get fresh token
            token = await client.get_token()
            assert token == "fresh-token-456"
            assert mock_client.post.call_count == 1

    @pytest.mark.skipif(not redox_env_available, reason="REDOX_CLIENT_ID environment variable not set")
    @pytest.mark.asyncio
    async def test_send_message_success(self, client):
        """Test successful message sending."""
        # Mock token and message response
        with (
            patch.object(client, "get_token", return_value="test-token") as mock_get_token,
            patch("httpx.AsyncClient") as mock_client_class,
        ):

            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={"status": "success", "id": "msg-123"})
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            payload = {"test": "data"}
            result = await client.send_message(payload)

            assert result == {"status": "success", "id": "msg-123"}
            mock_get_token.assert_called_once()

            # Verify the POST call
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://test.api.example.com/message"
            assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"
            assert call_args[1]["json"] == payload

    @pytest.mark.skipif(not redox_env_available, reason="REDOX_CLIENT_ID environment variable not set")
    @pytest.mark.asyncio
    async def test_send_message_error(self, client):
        """Test message sending with API error."""
        with patch.object(client, "get_token", return_value="test-token"), patch("httpx.AsyncClient") as mock_client_class:

            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 400
            mock_response.json = Mock(return_value={"error": "invalid_request"})
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            payload = {"test": "data"}

            with pytest.raises(RuntimeError, match="API request failed 400"):
                await client.send_message(payload)

    @pytest.mark.skipif(not redox_env_available, reason="REDOX_CLIENT_ID environment variable not set")
    @pytest.mark.asyncio
    async def test_send_patient_admin_message(self, client):
        """Test sending PatientAdmin message with proper payload structure."""
        with patch.object(client, "send_message") as mock_send_message:
            mock_send_message.return_value = {"status": "sent"}

            patient_data = {
                "Patient": {
                    "Identifiers": [{"ID": "MRN123", "IDType": "MRN"}],
                    "Demographics": {"FirstName": "John", "LastName": "Doe", "DOB": "1990-01-01"},
                }
            }

            result = await client.send_patient_admin_message(patient_data, "NewPatient")

            assert result == {"status": "sent"}

            # Verify the payload structure
            call_args = mock_send_message.call_args
            payload = call_args[0][0]

            assert payload["Meta"]["DataModel"] == "PatientAdmin"
            assert payload["Meta"]["EventType"] == "NewPatient"
            assert payload["Meta"]["Test"] is True
            assert "EventDateTime" in payload["Meta"]
            assert payload["Patient"] == patient_data["Patient"]

    @pytest.mark.skipif(not redox_env_available, reason="REDOX_CLIENT_ID environment variable not set")
    def test_is_token_valid(self, client):
        """Test token validity checking."""
        # No token
        assert not client._is_token_valid()

        # Valid token
        client._cached_token = {"access_token": "token"}
        client._token_expires_at = time.time() + 100
        assert client._is_token_valid()

        # Expired token
        client._token_expires_at = time.time() - 100
        assert not client._is_token_valid()

        # Token expiring soon (within 30 seconds)
        client._token_expires_at = time.time() + 25
        assert not client._is_token_valid()
