# Service Level Objectives (SLOs) & Self-Healing

This document defines Service Level Objectives (SLOs) for the HealthtechParseMatch API and implements basic self-healing capabilities.

## Service Level Objectives

### API Performance SLOs

| Metric | Target SLO | Time Window | Error Budget |
|--------|------------|-------------|--------------|
| **Success Rate** | 99.5% | 30 days | 3.5 hours downtime |
| **P95 Latency** | < 2 seconds | 30 days | - |
| **P99 Latency** | < 5 seconds | 30 days | - |

### Error Budget Calculation

For 99.5% success rate over 30 days:
- Total time: 30 × 24 × 3600 = 2,592,000 seconds
- Allowed downtime: 2,592,000 × (1 - 0.995) = 12,960 seconds (3.6 hours)
- Error budget: 12,960 seconds of downtime per 30 days

## Self-Healing Mechanisms

### 1. Retry Logic with Exponential Backoff

The system implements intelligent retry logic for transient failures:

- **Retryable Errors**: Network timeouts, 5xx HTTP errors, connection failures
- **Non-Retryable Errors**: 4xx HTTP errors, authentication failures
- **Backoff Strategy**: Exponential backoff with jitter (1s, 2s, 4s, 8s max)
- **Max Retries**: 3 attempts per request

### 2. Circuit Breaker Pattern

Implements circuit breaker to prevent cascade failures:

- **Failure Threshold**: 50% failure rate over 10 requests
- **Recovery Timeout**: 30 seconds in open state
- **Half-Open Testing**: Single request allowed after timeout

### 3. Fail-Open Policies

For critical patient matching operations:

- **Degraded Mode**: Fall back to simplified matching logic
- **Cache Utilization**: Use cached results when backend unavailable
- **Graceful Degradation**: Return partial results with warnings

### 4. Dead Letter Queue (DLQ)

Failed requests are captured for analysis:

- **Storage**: JSON files in `logs/dlq/` directory
- **Retention**: 7 days with automatic cleanup
- **Analysis**: Structured format for debugging and replay

## Monitoring & Alerting

### SLO Tracking Metrics

```prometheus
# Success Rate SLO
slo_success_rate_ratio = rate(redox_requests_total{status="success"}[30d]) / rate(redox_requests_total[30d])

# Latency SLOs
slo_p95_latency_seconds = histogram_quantile(0.95, rate(redox_request_duration_seconds_bucket[30d]))
slo_p99_latency_seconds = histogram_quantile(0.99, rate(redox_request_duration_seconds_bucket[30d]))

# Error Budget Burn Rate
error_budget_burn_rate = (1 - slo_success_rate_ratio) / (1 - 0.995)
```

### Alerting Rules

```yaml
# Error Budget Alerts
- alert: SLOErrorBudgetBurning
  expr: error_budget_burn_rate > 10
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Error budget burning too fast"

- alert: SLOErrorBudgetCritical
  expr: error_budget_burn_rate > 20
  for: 30m
  labels:
    severity: critical
  annotations:
    summary: "Error budget critically low"

# Latency Alerts
- alert: SLOLatencyViolation
  expr: slo_p95_latency_seconds > 2
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "P95 latency exceeding SLO"
```

## Implementation Details

### Retry Logic Implementation

```python
import asyncio
import random
from typing import Callable, Any, Optional

class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 8.0
    backoff_factor: float = 2.0
    jitter: bool = True

async def retry_with_backoff(
    func: Callable,
    config: RetryConfig = RetryConfig(),
    *args,
    **kwargs
) -> Any:
    """Execute function with exponential backoff retry logic."""
    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if attempt == config.max_attempts - 1:
                raise last_exception

            # Calculate delay with exponential backoff
            delay = min(config.base_delay * (config.backoff_factor ** attempt), config.max_delay)

            # Add jitter to prevent thundering herd
            if config.jitter:
                delay = delay * (0.5 + random.random() * 0.5)

            await asyncio.sleep(delay)

    raise last_exception
```

### Circuit Breaker Implementation

```python
from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        expected_exception: Exception = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenException()

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
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
```

## Testing SLO Compliance

### Load Testing

```bash
# Run load test to verify SLO compliance
ab -n 1000 -c 10 http://localhost:8000/patient/match

# Check metrics endpoint
curl http://localhost:8000/health/metrics | grep redox
```

### SLO Dashboard Panels

The Grafana dashboard includes SLO tracking panels:

- **Error Budget Burn Rate**: Shows how fast the error budget is being consumed
- **SLO Status Indicators**: Green/Yellow/Red status for each SLO
- **Latency Distribution**: Shows P50/P95/P99 against SLO targets
- **Success Rate Trends**: 30-day success rate with SLO target line

## Operational Runbooks

### Error Budget Burn Rate > 10 (Warning)

1. Check recent deployment history
2. Review error logs for patterns
3. Check upstream service health
4. Consider rolling back recent changes
5. Increase monitoring frequency

### Error Budget Burn Rate > 20 (Critical)

1. **IMMEDIATE ACTION**: Assess blast radius
2. Consider fail-open mode activation
3. Notify stakeholders
4. Implement emergency mitigation
5. Schedule post-mortem analysis

### Latency SLO Violation

1. Check system resource utilization
2. Review recent traffic patterns
3. Analyze slow query logs
4. Consider scaling adjustments
5. Optimize performance bottlenecks

## Future Enhancements

- **Automated Remediation**: Auto-scaling based on SLO violations
- **Multi-Region Failover**: Cross-region redundancy for high availability
- **Advanced Circuit Breaking**: Adaptive thresholds based on traffic patterns
- **Predictive Alerting**: ML-based anomaly detection for early warning</content>
<parameter name="filePath">c:\repo\HealthtechParseMatch\docs\slo.md
