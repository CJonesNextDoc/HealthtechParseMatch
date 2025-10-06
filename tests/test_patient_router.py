"""
Tests for patient router endpoints
"""

import httpx
import pytest
from httpx import AsyncClient

from app.main import app as fastapi_app


@pytest.fixture
async def client():
    """Get test client"""
    async with AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_patient_match_success(client):
    """Test successful patient match request"""
    payload = {"dob": "1990-01-01", "zip": "12345"}

    response = await client.post("/patient/match", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Patient matching completed (demo mode)" in data["message"]
    assert "matches" in data
    assert "processing_time_ms" in data


@pytest.mark.asyncio
async def test_patient_match_minimal_payload(client):
    """Test patient match with minimal required payload"""
    payload = {"dob": "1990-01-01", "zip": "12345"}

    response = await client.post("/patient/match", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_patient_match_with_optional_fields(client):
    """Test patient match with optional fields"""
    payload = {"dob": "1990-01-01", "zip": "12345", "last4_phone": "1234", "last_name_prefix": "Dr", "first_initial": "J"}

    response = await client.post("/patient/match", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_patient_match_missing_required_fields(client):
    """Test patient match with missing required fields"""
    # Missing zip
    payload = {"dob": "1990-01-01"}

    response = await client.post("/patient/match", json=payload)

    # Should return 422 validation error for missing required field
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patient_match_metrics_generation(client):
    """Test that patient match generates Prometheus metrics"""
    payload = {"dob": "1990-01-01", "zip": "12345"}

    # Make the request
    response = await client.post("/patient/match", json=payload)
    assert response.status_code == 200

    # Check that metrics endpoint is accessible
    metrics_response = await client.get("/health/metrics")
    assert metrics_response.status_code == 200

    metrics_text = metrics_response.text
    # Should contain redox metrics
    assert "redox_requests_total" in metrics_text
    assert 'method="get_patients"' in metrics_text
