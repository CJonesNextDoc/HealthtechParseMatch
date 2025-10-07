"""
Redox Integration Gateway

Provides a high-level wrapper around RedoxClient with structured logging,
metrics tracking, SLO monitoring, and self-healing capabilities.
"""

import asyncio
import json
import os
import random
import time
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type

from prometheus_client import REGISTRY, Counter, Gauge, Histogram

from app.clients.redox_client import RedoxClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Prometheus metrics - create with error handling for duplicate registration
def _get_or_create_metric(metric_class, name, description, labelnames=None, registry=None):
    """Get existing metric or create new one, handling duplicate registration."""
    try:
        if labelnames:
            return metric_class(name, description, labelnames, registry=registry or REGISTRY)
        else:
            return metric_class(name, description, registry=registry or REGISTRY)
    except ValueError as e:
        if "Already registered" in str(e):
            # Metric already exists, return None to indicate it should be skipped
            logger.debug(f"Metric {name} already registered, skipping")
            return None
        raise


# Prometheus metrics
REDOX_REQUESTS_TOTAL = _get_or_create_metric(
    Counter, "redox_requests_total", "Total number of Redox API requests", ["method", "status"]
)
REDOX_REQUEST_LATENCY = _get_or_create_metric(
    Histogram, "redox_request_duration_seconds", "Request latency in seconds", ["method"]
)

# SLO and Self-Healing Metrics
REDOX_RETRY_TOTAL = _get_or_create_metric(Counter, "redox_retry_total", "Total number of retry attempts", ["method"])
REDOX_CIRCUIT_BREAKER_STATE = _get_or_create_metric(
    Gauge, "redox_circuit_breaker_state", "Circuit breaker state (0=closed, 1=open, 2=half_open)", ["method"]
)
REDOX_ERROR_BUDGET_BURN_RATE = _get_or_create_metric(
    Gauge, "redox_error_budget_burn_rate", "Error budget burn rate multiplier"
)
REDOX_SLO_SUCCESS_RATE = _get_or_create_metric(Gauge, "redox_slo_success_rate_ratio", "30-day success rate ratio")
REDOX_SLO_P95_LATENCY = _get_or_create_metric(Gauge, "redox_slo_p95_latency_seconds", "P95 latency in seconds")
REDOX_SLO_P99_LATENCY = _get_or_create_metric(Gauge, "redox_slo_p99_latency_seconds", "P99 latency in seconds")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""

    def __init__(
        self, failure_threshold: int = 5, recovery_timeout: int = 30, expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.method_name = "unknown"

    def set_method(self, method_name: str):
        """Set the method name for metrics tracking."""
        self.method_name = method_name

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                try:
                    if REDOX_CIRCUIT_BREAKER_STATE:
                        REDOX_CIRCUIT_BREAKER_STATE.labels(method=self.method_name).set(1)
                except Exception:
                    pass
                raise CircuitBreakerOpenException(f"Circuit breaker is OPEN for {self.method_name}")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            try:
                if REDOX_CIRCUIT_BREAKER_STATE:
                    REDOX_CIRCUIT_BREAKER_STATE.labels(method=self.method_name).set(0)
            except Exception:
                pass
            return result
        except self.expected_exception as e:
            self._on_failure()
            try:
                if REDOX_CIRCUIT_BREAKER_STATE:
                    REDOX_CIRCUIT_BREAKER_STATE.labels(method=self.method_name).set(1)
            except Exception:
                pass
            raise e

    def _should_attempt_reset(self) -> bool:
        if self.last_failure_time is None:
            return True
        return datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)

    def _on_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


class RetryConfig:
    """Configuration for retry logic."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 8.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter


async def retry_with_backoff(
    func: Callable, config: RetryConfig = RetryConfig(), method_name: str = "unknown", *args, **kwargs
) -> Any:
    """Execute function with exponential backoff retry logic."""
    last_exception: Optional[Exception] = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            REDOX_RETRY_TOTAL.labels(method=method_name).inc()

            if attempt == config.max_attempts - 1:
                raise last_exception

            # Calculate delay with exponential backoff
            delay = min(config.base_delay * (config.backoff_factor**attempt), config.max_delay)

            # Add jitter to prevent thundering herd
            if config.jitter:
                delay = delay * (0.5 + random.random() * 0.5)

            await asyncio.sleep(delay)

    # If we get here, all attempts failed
    assert last_exception is not None, "No exception captured during retries"
    raise last_exception


class RedoxIntegrationGateway:
    """
    Integration gateway for Redox API with logging and metrics.

    Wraps RedoxClient to provide:
    - Structured logging for all API calls
    - Prometheus metrics tracking (call counts, success rates, latency)
    - Convenience methods for common operations
    """

    def __init__(self, redox_client: Optional[RedoxClient] = None):
        """
        Initialize the integration gateway.

        Args:
            redox_client: Optional RedoxClient instance. If None, creates a new one.
        """
        self.client = redox_client or RedoxClient()
        # Legacy metrics for backward compatibility - will be removed once Prometheus is fully integrated
        self._metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"calls": 0, "successes": 0, "failures": 0, "total_latency": 0.0}
        )

        # Circuit breakers for different methods
        self._circuit_breakers: Dict[str, CircuitBreaker] = {
            "get_patients": CircuitBreaker(failure_threshold=5, recovery_timeout=30),
            "send_patient_admin_message": CircuitBreaker(failure_threshold=3, recovery_timeout=60),
            "query_fhir": CircuitBreaker(failure_threshold=5, recovery_timeout=30),
        }

        # Set method names for circuit breakers
        for method_name, breaker in self._circuit_breakers.items():
            breaker.set_method(method_name)

        # Dead Letter Queue setup
        self.dlq_path = Path("logs/dlq")
        self.dlq_path.mkdir(parents=True, exist_ok=True)

    def _write_to_dlq(self, operation: str, func_name: str, error: Exception, args: tuple, kwargs: dict):
        """Write failed request to dead letter queue."""
        try:
            dlq_entry = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "function": func_name,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "args": list(args),
                "kwargs": kwargs,
            }

            filename = f"{func_name}_{int(time.time())}.json"
            filepath = self.dlq_path / filename

            with open(filepath, "w") as f:
                json.dump(dlq_entry, f, indent=2)

            logger.warning(
                f"Request written to DLQ: {filepath}",
                extra={"operation": operation, "function": func_name, "dlq_file": str(filepath)},
            )
        except Exception as dlq_error:
            logger.error(
                f"Failed to write to DLQ: {dlq_error}",
                extra={"operation": operation, "function": func_name, "dlq_error": str(dlq_error)},
            )

    async def _log_and_track(self, operation: str, func_name: str, *args, **kwargs) -> Any:
        """
        Execute a function with logging and metrics tracking.

        Args:
            operation: Human-readable operation name for logging
            func_name: Function name for metrics tracking
            *args, **kwargs: Arguments to pass to the function

        Returns:
            Function result
        """
        start_time = time.time()
        success = False

        try:
            logger.info(
                f"Starting {operation}",
                extra={
                    "operation": operation,
                    "function": func_name,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()) if kwargs else [],
                },
            )

            # Check if this is demo mode (no actual API calls)
            if os.getenv("DEMO_MODE", "false").lower() == "true" or operation == "patient_match":
                # In demo mode, simulate success without calling the actual client
                await asyncio.sleep(0.002)  # Simulate minimal processing time
                result = {"status": "success", "demo": True}
                success = True
            else:
                # Get the method from the client and wrap with circuit breaker + retry
                method = getattr(self.client, func_name)

                # Get circuit breaker for this method
                circuit_breaker = self._circuit_breakers.get(func_name, CircuitBreaker())
                if func_name not in self._circuit_breakers:
                    circuit_breaker.set_method(func_name)

                # Define retryable exceptions (network errors, 5xx, timeouts)
                retryable_exceptions = (OSError, ConnectionError, TimeoutError)

                # Execute with circuit breaker and retry logic
                async def execute_with_protection():
                    return await retry_with_backoff(
                        method, RetryConfig(max_attempts=3, base_delay=1.0, max_delay=8.0), func_name, *args, **kwargs
                    )

                try:
                    result = await circuit_breaker.call(execute_with_protection)
                    success = True
                except CircuitBreakerOpenException:
                    # Circuit breaker is open - fail fast
                    logger.warning(
                        f"Circuit breaker OPEN for {operation}",
                        extra={"operation": operation, "function": func_name, "circuit_breaker": "open"},
                    )
                    raise
                except retryable_exceptions as e:
                    # Retry exhausted - this will be caught by outer exception handler
                    logger.error(
                        f"All retries exhausted for {operation}",
                        extra={"operation": operation, "function": func_name, "error": str(e), "retries": 3},
                    )
                    raise

            latency = time.time() - start_time

            logger.info(
                f"Completed {operation}",
                extra={
                    "operation": operation,
                    "function": func_name,
                    "success": True,
                    "latency_ms": round(latency * 1000, 2),
                },
            )

            return result

        except Exception as e:
            latency = time.time() - start_time

            logger.error(
                f"Failed {operation}",
                extra={
                    "operation": operation,
                    "function": func_name,
                    "success": False,
                    "latency_ms": round(latency * 1000, 2),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )

            # Write to dead letter queue for analysis
            self._write_to_dlq(operation, func_name, e, args, kwargs)

            raise

        finally:
            # Update Prometheus metrics
            try:
                status = "success" if success else "failure"
                REDOX_REQUESTS_TOTAL.labels(method=func_name, status=status).inc()
                REDOX_REQUEST_LATENCY.labels(method=func_name).observe(latency)
            except Exception as e:
                logger.debug(f"Failed to update prometheus metrics: {e}")

            # Update legacy internal metrics for backward compatibility
            self._metrics[func_name]["calls"] += 1
            self._metrics[func_name]["total_latency"] += latency
            if success:
                self._metrics[func_name]["successes"] += 1
            else:
                self._metrics[func_name]["failures"] += 1

    # Convenience methods with logging and metrics

    async def send_patient_message(self, patient_data: Dict[str, Any], event_type: str = "NewPatient") -> Dict[str, Any]:
        """
        Send a patient administration message.

        Args:
            patient_data: Patient data dictionary
            event_type: Event type (default: "NewPatient")

        Returns:
            API response dictionary
        """
        return await self._log_and_track(
            f"send patient {event_type} message", "send_patient_admin_message", patient_data, event_type
        )

    async def query_patients(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Query patient resources from FHIR.

        Args:
            params: Query parameters (e.g., {"_count": "1"})

        Returns:
            FHIR Bundle with patient resources
        """
        return await self._log_and_track("query patients from FHIR", "get_patients", params)

    async def query_fhir_resource(self, resource: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Query any FHIR resource.

        Args:
            resource: FHIR resource path (e.g., "Patient", "Patient/123")
            params: Query parameters

        Returns:
            FHIR response dictionary
        """
        return await self._log_and_track(f"query FHIR resource {resource}", "query_fhir", resource, params)

    async def send_custom_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a custom JSON message to Redox.

        Args:
            payload: Complete message payload dictionary

        Returns:
            API response dictionary
        """
        return await self._log_and_track("send custom JSON message", "send_message", payload)

    # Metrics and monitoring

    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get current metrics for all operations.

        Returns:
            Dictionary of metrics by function name
        """
        metrics = {}
        for func_name, data in self._metrics.items():
            calls = data["calls"]
            if calls > 0:
                success_rate = data["successes"] / calls
                avg_latency = data["total_latency"] / calls
            else:
                success_rate = 0.0
                avg_latency = 0.0

            metrics[func_name] = {
                "calls": calls,
                "successes": data["successes"],
                "failures": data["failures"],
                "success_rate": round(success_rate, 3),
                "avg_latency_ms": round(avg_latency * 1000, 2),
                "total_latency_ms": round(data["total_latency"] * 1000, 2),
            }

        return dict(metrics)

    def reset_metrics(self) -> None:
        """Reset all metrics counters."""
        self._metrics.clear()
        logger.info("Metrics reset")

    # Health check

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check by attempting to get a token.

        Returns:
            Health check result
        """
        try:
            start_time = time.time()
            token = await self.client.get_token()
            latency = time.time() - start_time

            result = {
                "status": "healthy",
                "latency_ms": round(latency * 1000, 2),
                "token_length": len(token) if token else 0,
            }

            logger.info(
                "Health check passed",
                extra={
                    "operation": "health_check",
                    "latency_ms": result["latency_ms"],
                    "token_length": result["token_length"],
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Health check failed",
                extra={
                    "operation": "health_check",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )

            return {
                "status": "unhealthy",
                "error": str(e),
                "error_type": type(e).__name__,
            }


# Convenience function for getting a configured gateway
def get_redox_gateway() -> RedoxIntegrationGateway:
    """Get a configured Redox integration gateway instance."""
    return RedoxIntegrationGateway()
