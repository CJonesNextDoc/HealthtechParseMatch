"""
Redox Integration Gateway

Provides a high-level wrapper around RedoxClient with structured logging,
metrics tracking, and convenience methods for healthcare integrations.
"""

import time
from collections import defaultdict
from typing import Any, Dict, Optional

from prometheus_client import Counter, Histogram

from app.clients.redox_client import RedoxClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Prometheus metrics
REDOX_REQUESTS_TOTAL = Counter("redox_requests_total", "Total number of Redox API requests", ["method", "status"])

REDOX_REQUEST_LATENCY = Histogram("redox_request_duration_seconds", "Request latency in seconds", ["method"])


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

            # Get the method from the client
            method = getattr(self.client, func_name)
            result = await method(*args, **kwargs)

            success = True
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

            raise

        finally:
            # Update Prometheus metrics
            status = "success" if success else "failure"
            REDOX_REQUESTS_TOTAL.labels(method=func_name, status=status).inc()
            REDOX_REQUEST_LATENCY.labels(method=func_name).observe(latency)

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
