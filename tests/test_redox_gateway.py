"""
Tests for Redox Integration Gateway
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import generate_latest

from app.integrations.redox_gateway import (
    CircuitBreaker,
    CircuitBreakerOpenException,
    CircuitState,
    RedoxIntegrationGateway,
    RetryConfig,
    retry_with_backoff,
)


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


@pytest.mark.asyncio
async def test_demo_mode_patient_match(gateway, mock_redox_client):
    """Test demo mode for patient_match operation."""
    # Test that patient_match operation uses demo mode without calling client
    result = await gateway._log_and_track("patient_match", "get_patients", {})

    # Should return demo result without calling the client
    assert result == {"status": "success", "demo": True}
    # Client method should not be called
    mock_redox_client.get_patients.assert_not_called()

    # Check that success metrics were recorded
    metrics_output = generate_latest().decode("utf-8")
    assert 'redox_requests_total{method="get_patients",status="success"}' in metrics_output


@pytest.mark.asyncio
async def test_demo_mode_env_var(gateway, mock_redox_client):
    """Test demo mode via environment variable."""
    import os

    # Set demo mode via environment variable
    original_env = os.environ.get("DEMO_MODE")
    os.environ["DEMO_MODE"] = "true"

    try:
        result = await gateway._log_and_track("some_operation", "get_patients", {})

        # Should return demo result
        assert result == {"status": "success", "demo": True}
        mock_redox_client.get_patients.assert_not_called()
    finally:
        # Restore original environment
        if original_env is None:
            os.environ.pop("DEMO_MODE", None)
        else:
            os.environ["DEMO_MODE"] = original_env


def test_get_redox_gateway():
    """Test the convenience function."""
    from app.integrations.redox_gateway import get_redox_gateway

    mock_client = MagicMock()
    with patch("app.integrations.redox_gateway.RedoxClient", return_value=mock_client):
        gateway = get_redox_gateway()
        assert isinstance(gateway, RedoxIntegrationGateway)
        # Should create a new RedoxClient instance
        assert gateway.client is mock_client


@pytest.mark.asyncio
async def test_dlq_writes_on_failure(gateway, mock_redox_client, tmp_path):
    """Test that failed requests are written to dead letter queue."""
    import json

    # Mock the client to raise an exception
    mock_redox_client.send_patient_admin_message.side_effect = RuntimeError("API Error")

    # Override the DLQ path for testing
    gateway.dlq_path = tmp_path / "dlq"
    gateway.dlq_path.mkdir(parents=True, exist_ok=True)

    with pytest.raises(RuntimeError, match="API Error"):
        await gateway.send_patient_message({"name": "John Doe"})

    # Check that DLQ file was created
    dlq_files = list(gateway.dlq_path.glob("*.json"))
    assert len(dlq_files) == 1

    # Check DLQ file contents
    dlq_file = dlq_files[0]
    with open(dlq_file, "r") as f:
        dlq_entry = json.load(f)

    assert dlq_entry["operation"] == "send patient NewPatient message"
    assert dlq_entry["function"] == "send_patient_admin_message"
    assert dlq_entry["error_type"] == "RuntimeError"
    assert dlq_entry["error_message"] == "API Error"
    assert "timestamp" in dlq_entry
    assert dlq_entry["args"] == [{"name": "John Doe"}, "NewPatient"]
    assert dlq_entry["kwargs"] == {}


@pytest.mark.asyncio
async def test_circuit_breaker_open_exception_handling(gateway, mock_redox_client):
    """Test that circuit breaker open exceptions are properly handled."""
    # Get the circuit breaker for this method
    circuit_breaker = gateway._circuit_breakers["send_patient_admin_message"]

    # Force circuit breaker to open state and ensure it won't attempt reset
    circuit_breaker.state = CircuitState.OPEN
    circuit_breaker.last_failure_time = datetime.now()  # Recent failure, won't attempt reset

    # This should raise CircuitBreakerOpenException without calling the client
    with pytest.raises(CircuitBreakerOpenException, match="Circuit breaker is OPEN"):
        await gateway.send_patient_message({"name": "John Doe"})

    # Client should not be called
    mock_redox_client.send_patient_admin_message.assert_not_called()


@pytest.mark.asyncio
async def test_retry_exhausted_exception_handling(gateway, mock_redox_client):
    """Test that retry exhausted exceptions are properly handled."""
    # Mock the client to always raise a retryable exception
    mock_redox_client.send_patient_admin_message.side_effect = ConnectionError("Network Error")

    with pytest.raises(ConnectionError, match="Network Error"):
        await gateway.send_patient_message({"name": "John Doe"})


@pytest.mark.asyncio
async def test_circuit_breaker_state_transitions():
    """Test circuit breaker state transitions and internal methods."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30)
    cb.set_method("test_method")

    # Test initial state
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0

    # Test _on_failure transitions
    cb._on_failure()
    assert cb.failure_count == 1
    assert cb.state == CircuitState.CLOSED

    cb._on_failure()
    assert cb.failure_count == 2
    assert cb.state == CircuitState.OPEN

    # Test _should_attempt_reset
    assert not cb._should_attempt_reset()  # Too soon

    # Simulate time passing
    cb.last_failure_time = datetime.now() - timedelta(seconds=31)
    assert cb._should_attempt_reset()  # Recovery timeout passed

    # Test _on_success resets state
    cb._on_success()
    assert cb.failure_count == 0
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_retry_with_jitter():
    """Test that retry logic includes jitter."""
    import asyncio

    call_count = 0

    async def failing_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Temporary failure")
        return "success"

    # Mock sleep to capture delay times
    sleep_times = []
    original_sleep = asyncio.sleep

    async def mock_sleep(delay):
        sleep_times.append(delay)
        await original_sleep(0.001)  # Minimal actual sleep

    with patch("asyncio.sleep", side_effect=mock_sleep):
        result = await retry_with_backoff(failing_func, RetryConfig(max_attempts=3, base_delay=1.0, jitter=True))

    assert result == "success"
    assert call_count == 3
    assert len(sleep_times) == 2  # Two retries

    # With jitter enabled, delays should vary
    # Base delays would be 1.0 and 2.0, but with jitter they should be different
    assert sleep_times[0] != 1.0 or sleep_times[1] != 2.0


@pytest.mark.asyncio
async def test_dlq_write_failure_handling(gateway, mock_redox_client, tmp_path):
    """Test that DLQ write failures are handled gracefully."""
    # Mock the client to raise an exception
    mock_redox_client.send_patient_admin_message.side_effect = RuntimeError("API Error")

    # Override DLQ path to a location that will cause write failure
    gateway.dlq_path = tmp_path / "nonexistent" / "dlq"  # Directory doesn't exist and can't be created

    with pytest.raises(RuntimeError, match="API Error"):
        await gateway.send_patient_message({"name": "John Doe"})

    # Should still raise the original error, not a DLQ error


def test_metrics_calculation_edge_cases(gateway):
    """Test metrics calculation with zero calls."""
    # Reset metrics
    gateway._metrics = defaultdict(lambda: {"calls": 0, "successes": 0, "failures": 0, "total_latency": 0.0})

    # Test with zero calls - should return empty dict since no methods have been called
    metrics = gateway.get_metrics()
    assert isinstance(metrics, dict)
    # When no methods have been called, metrics should be empty
    assert len(metrics) == 0
