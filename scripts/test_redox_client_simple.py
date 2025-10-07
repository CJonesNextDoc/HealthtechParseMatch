#!/usr/bin/env python3
"""
Simple test runner for RedoxClient to verify basic functionality.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

from dotenv import load_dotenv

from app.clients.redox_client import RedoxClient

load_dotenv()


async def test_redox_client():
    """Run basic RedoxClient tests."""
    # Sample JWK for testing
    sample_jwk = {
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

    # Create client
    client = RedoxClient(
        client_id="test-client-id",
        private_jwk=sample_jwk,
        token_url="https://test.auth.example.com/token",
        endpoint_url="https://test.api.example.com",
        token_cache_duration=300,
    )

    print("✅ Client initialization")

    # Test assertion generation
    assertion = client._generate_assertion()
    assert isinstance(assertion, str)
    assert len(assertion.split(".")) == 3  # JWT has 3 parts
    print("✅ JWT assertion generation")

    # Test token caching
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

    print("✅ Token caching")

    # Test message sending
    with patch.object(client, "get_token", return_value="test-token"), patch("httpx.AsyncClient") as mock_client_class:

        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"status": "success", "id": "msg-123"})
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        payload = {"test": "data"}
        result = await client.send_message(payload)

        assert result == {"status": "success", "id": "msg-123"}

    print("✅ Message sending")

    # Test patient admin message
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

    print("✅ Patient admin message")

    print("\n🎉 All RedoxClient tests passed!")


if __name__ == "__main__":
    asyncio.run(test_redox_client())
