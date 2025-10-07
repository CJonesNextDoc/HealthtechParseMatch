# SLO Integration Tests

This directory contains integration tests for the SLO (Service Level Objectives) monitoring and self-healing features.

## Overview

The integration tests verify that the complete SLO monitoring pipeline works end-to-end:

- **API Service**: FastAPI application with SLO metrics
- **Prometheus**: Metrics collection and querying
- **Grafana**: Dashboard visualization and alerting
- **Self-Healing**: Circuit breaker, retry logic, and DLQ functionality

## Test Files

- `test_integration_slo.py`: Pytest-based integration tests using Docker containers
- `scripts/run_integration_tests.py`: Standalone integration test runner

## Running Integration Tests

### Prerequisites

- Docker and Docker Compose installed
- Python 3.13+
- pytest-docker (for pytest-based tests)

### Method 1: Standalone Runner (Recommended)

```bash
cd /path/to/HealthtechParseMatch
python scripts/run_integration_tests.py
```

This will:
1. Start all Docker services (API, Prometheus, Grafana)
2. Wait for services to be ready
3. Run comprehensive tests against each service
4. Verify SLO metrics collection and dashboard provisioning
5. Clean up containers when done

### Method 2: Pytest with Docker

```bash
cd /path/to/HealthtechParseMatch
pip install pytest-docker
pytest tests/test_integration_slo.py -v --tb=short
```

Note: Requires `docker-compose.yml` in the project root and proper pytest-docker configuration.

## Test Coverage

The integration tests verify:

### API Service Tests
- Health endpoint responsiveness
- Metrics endpoint accessibility
- Patient matching functionality (demo mode)
- SLO metrics generation

### Prometheus Tests
- Service readiness and health
- Metrics collection from API service
- SLO-specific metric queries:
  - `redox_requests_total`
  - `redox_request_duration_seconds`
  - `redox_circuit_breaker_state`
  - Latency percentiles and success rates

### Grafana Tests
- Service health and accessibility
- Dashboard provisioning (SLO Dashboard)
- Datasource configuration (Prometheus connection)

### Load Tests
- Concurrent request handling
- Circuit breaker behavior under load
- Monitoring stack resilience

## Configuration

### Docker Services

The tests use the following services defined in `docker-compose.yml`:

- **api**: FastAPI application (port 8000)
- **prometheus**: Metrics collection (port 9090)
- **grafana**: Dashboard visualization (port 3000)

### Environment Variables

- `DEMO_MODE=true`: Enables demo mode for testing without external dependencies
- `GF_SECURITY_ADMIN_PASSWORD=admin`: Grafana admin password

## Troubleshooting

### Common Issues

1. **Docker not available**: Ensure Docker Desktop is running
2. **Port conflicts**: Stop any services using ports 8000, 9090, 3000
3. **Build failures**: Check Dockerfile and ensure all dependencies are available
4. **Service timeouts**: Increase timeout values in test configuration

### Debug Mode

Run with verbose output:

```bash
python scripts/run_integration_tests.py 2>&1 | tee integration_test.log
```

### Manual Testing

Start services manually:

```bash
docker-compose up -d
```

Then test individual components:

```bash
# Test API
curl http://localhost:8000/health

# Test Prometheus
curl http://localhost:9090/-/ready

# Test Grafana
curl http://localhost:3000/api/health
```

## Expected Results

When all tests pass, you should see:

```
🎉 All integration tests passed!
  API Service: ✅ PASS
  Prometheus Service: ✅ PASS
  Grafana Service: ✅ PASS
```

This confirms that the SLO monitoring and self-healing features are working correctly in a production-like environment.
