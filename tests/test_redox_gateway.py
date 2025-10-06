"""
Tests for Redox Integration Gateway
"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import generate_latest

from app.integrations.redox_gateway import RedoxIntegrationGateway


@pytest.fixture
def mock_redox_client():
    """Mock RedoxClient for testing."""
    client = MagicMock()
    client.send_patient_admin_message = AsyncMock()
    client.get_patients = AsyncMock()
    client.query_fhir = AsyncMock()
    client.send_message = AsyncMock()
    client.get_token = AsyncMock(return_value="mock-token")
    return client


@pytest.fixture
def gateway(mock_redox_client):
    """Gateway instance with mocked client."""
    return RedoxIntegrationGateway(mock_redox_client)


@pytest.mark.asyncio
async def test_send_patient_message_success(gateway, mock_redox_client):
    """Test successful patient message sending."""
    mock_redox_client.send_patient_admin_message.return_value = {"status": "success"}

    result = await gateway.send_patient_message({"name": "John Doe"}, "NewPatient")

    assert result == {"status": "success"}
    mock_redox_client.send_patient_admin_message.assert_called_once_with({"name": "John Doe"}, "NewPatient")


@pytest.mark.asyncio
async def test_send_patient_message_failure(gateway, mock_redox_client):
    """Test patient message sending failure."""
    mock_redox_client.send_patient_admin_message.side_effect = RuntimeError("API Error")

    with pytest.raises(RuntimeError, match="API Error"):
        await gateway.send_patient_message({"name": "John Doe"})


@pytest.mark.asyncio
async def test_query_patients_success(gateway, mock_redox_client):
    """Test successful patient querying."""
    mock_response = {"resourceType": "Bundle", "total": 1}
    mock_redox_client.get_patients.return_value = mock_response

    result = await gateway.query_patients({"_count": "1"})

    assert result == mock_response
    mock_redox_client.get_patients.assert_called_once_with({"_count": "1"})


@pytest.mark.asyncio
async def test_query_fhir_resource_success(gateway, mock_redox_client):
    """Test successful FHIR resource querying."""
    mock_response = {"resourceType": "Patient", "id": "123"}
    mock_redox_client.query_fhir.return_value = mock_response

    result = await gateway.query_fhir_resource("Patient/123")

    assert result == mock_response
    mock_redox_client.query_fhir.assert_called_once_with("Patient/123", None)


@pytest.mark.asyncio
async def test_send_custom_message_success(gateway, mock_redox_client):
    """Test successful custom message sending."""
    payload = {"Meta": {"DataModel": "Test"}, "data": "test"}
    mock_redox_client.send_message.return_value = {"status": "sent"}

    result = await gateway.send_custom_message(payload)

    assert result == {"status": "sent"}
    mock_redox_client.send_message.assert_called_once_with(payload)


@pytest.mark.asyncio
async def test_health_check_success(gateway, mock_redox_client):
    """Test successful health check."""
    mock_redox_client.get_token.return_value = "mock-jwt-token"

    result = await gateway.health_check()

    assert result["status"] == "healthy"
    assert "latency_ms" in result
    assert result["token_length"] == len("mock-jwt-token")


@pytest.mark.asyncio
async def test_health_check_failure(gateway, mock_redox_client):
    """Test health check failure."""
    mock_redox_client.get_token.side_effect = RuntimeError("Auth failed")

    result = await gateway.health_check()

    assert result["status"] == "unhealthy"
    assert "error" in result
    assert result["error_type"] == "RuntimeError"


def test_get_metrics_empty(gateway):
    """Test getting metrics when no calls have been made."""
    metrics = gateway.get_metrics()
    assert metrics == {}


def test_get_metrics_with_data(gateway, mock_redox_client):
    """Test getting metrics after some operations."""
    # Simulate some metrics data
    gateway._metrics["send_patient_admin_message"]["calls"] = 2
    gateway._metrics["send_patient_admin_message"]["successes"] = 1
    gateway._metrics["send_patient_admin_message"]["failures"] = 1
    gateway._metrics["send_patient_admin_message"]["total_latency"] = 0.1

    metrics = gateway.get_metrics()

    assert "send_patient_admin_message" in metrics
    data = metrics["send_patient_admin_message"]
    assert data["calls"] == 2
    assert data["successes"] == 1
    assert data["failures"] == 1
    assert data["success_rate"] == 0.5
    assert data["avg_latency_ms"] == 50.0  # 0.1 * 1000 / 2


def test_reset_metrics(gateway):
    """Test resetting metrics."""
    gateway._metrics["test_func"]["calls"] = 5
    assert len(gateway._metrics) > 0

    gateway.reset_metrics()
    assert len(gateway._metrics) == 0


@pytest.mark.asyncio
async def test_prometheus_metrics_success(gateway, mock_redox_client):
    """Test that Prometheus metrics are recorded for successful calls."""
    mock_redox_client.send_patient_admin_message.return_value = {"status": "success"}

    # Make a successful call
    await gateway.send_patient_message({"name": "John Doe"})

    # Check that metrics contain the expected labels and positive values
    metrics_output = generate_latest().decode("utf-8")
    assert 'redox_requests_total{method="send_patient_admin_message",status="success"}' in metrics_output
    assert 'redox_request_duration_seconds_count{method="send_patient_admin_message"}' in metrics_output

    # Extract and verify the counter value is positive
    counter_match = re.search(
        r'redox_requests_total\{method="send_patient_admin_message",status="success"\} (\d+\.?\d*)', metrics_output
    )
    assert counter_match, "Counter metric not found"
    counter_value = float(counter_match.group(1))
    assert counter_value >= 1.0, f"Counter value {counter_value} should be >= 1.0"


@pytest.mark.asyncio
async def test_prometheus_metrics_failure(gateway, mock_redox_client):
    """Test that Prometheus metrics are recorded for failed calls."""
    mock_redox_client.send_patient_admin_message.side_effect = RuntimeError("API Error")

    # Make a call that will fail
    with pytest.raises(RuntimeError):
        await gateway.send_patient_message({"name": "John Doe"})

    # Check that metrics contain the expected failure labels and positive values
    metrics_output = generate_latest().decode("utf-8")
    assert 'redox_requests_total{method="send_patient_admin_message",status="failure"}' in metrics_output

    # Extract and verify the failure counter value is positive
    counter_match = re.search(
        r'redox_requests_total\{method="send_patient_admin_message",status="failure"\} (\d+\.?\d*)', metrics_output
    )
    assert counter_match, "Failure counter metric not found"
    counter_value = float(counter_match.group(1))
    assert counter_value >= 1.0, f"Failure counter value {counter_value} should be >= 1.0"


@pytest.mark.asyncio
async def test_prometheus_metrics_multiple_methods(gateway, mock_redox_client):
    """Test that Prometheus metrics track different methods separately."""
    mock_redox_client.send_patient_admin_message.return_value = {"status": "success"}
    mock_redox_client.get_patients.return_value = {"resourceType": "Bundle"}

    # Make calls to different methods
    await gateway.send_patient_message({"name": "John Doe"})
    await gateway.query_patients()

    # Check that metrics contain both methods
    metrics_output = generate_latest().decode("utf-8")
    assert 'method="send_patient_admin_message"' in metrics_output
    assert 'method="get_patients"' in metrics_output


def test_get_redox_gateway():
    """Test the convenience function."""
    from app.integrations.redox_gateway import get_redox_gateway

    mock_client = MagicMock()
    with patch("app.integrations.redox_gateway.RedoxClient", return_value=mock_client):
        gateway = get_redox_gateway()
        assert isinstance(gateway, RedoxIntegrationGateway)
        # Should create a new RedoxClient instance
        assert gateway.client is mock_client
