# Product Roadmap

This document outlines the development roadmap for HealthtechParseMatch, organized by priority tiers. Items are moved to [FEATURES.md](FEATURES.md) as they are completed.

## Tier A — 100% "Easy Wins", Big Interview Signal

### 1. Observability (Metrics + Logs) in Redox Path
**Status:** ✅ **COMPLETED** - RedoxIntegrationGateway with structured logging and Prometheus metrics tracking
- Add Prometheus metrics to async client/service: counters, histograms for send/latency/retries
- Structured JSON logs with correlation IDs
- **Current Implementation:**
  - `RedoxIntegrationGateway` with `_log_and_track()` method
  - **Prometheus Metrics:**
    - `redox_requests_total` counter (method, status labels)
    - `redox_request_duration_seconds` histogram (method label)
  - Structured logging with request IDs via `RequestIdAdapter`
  - Health check endpoint for monitoring
  - `/health/metrics` endpoint exposing Prometheus metrics
- **Artifacts:** Metrics endpoint ready and tested
- **Why:** observability, SLAs, monitoring/alerting/self-healing

### 2. CI on GitHub Actions (Build, Test, Lint, Typecheck)
**Status:** ✅ **COMPLETED** - Comprehensive CI/CD pipeline
- Workflow: on PR, run pytest, ruff, mypy, and build a Docker image
- **Current Implementation:**
  - `.github/workflows/ci.yml`: pytest, ruff, mypy, pre-commit hooks
  - `.github/workflows/release.yml`: Docker image building
  - Quality checks: Black, Ruff, mypy, pytest
- **Artifacts:** ✅ Passing badges, green checks on PR, coverage reports
- **Why:** Best practices for CI/CD

### 3. Partner Onboarding Starter Kit (Docs + Postman + Sample App)
**Status:** ✅ **COMPLETED** - Comprehensive partner enablement tools
- docs/partners.md (how to auth, send PatientAdmin, read FHIR)
- Postman collection for API testing
- 30-line Python SDK wrapper (pip install -e .)
- **Current Implementation:**
  - `docs/partners.md`: Comprehensive API documentation with authentication, endpoints, examples, and error handling
  - `docs/postman_collection.json`: Postman collection with pre-configured requests for all major endpoints
  - `healthtech_sdk/`: Python SDK package with HealthtechClient class
    - `__init__.py`: Package exports
    - `client.py`: 30-line client with methods for health checks, patient matching, employee/project operations
    - `pyproject.toml`: Package configuration
    - `README.md`: SDK usage documentation
- **Artifacts:** Partner documentation, Postman collection, installable Python SDK
- **Why:** Developer experience, API integration, interview signal for SDK development skills

### 4. Grafana Dashboard for Metrics Visualization
**Status:** ✅ **COMPLETED** - Comprehensive Grafana dashboard for Redox API observability
- Create Grafana dashboard JSON for Redox metrics
- Include panels for request rates, latency percentiles, success rates
- Add screenshots to documentation
- **Current Implementation:**
  - `docs/grafana_dashboard.json`: Complete dashboard with 8 panels
    - Request Rate (per second) - time series graph
    - Success Rate (%) - percentage over time
    - Request Latency Percentiles - P50/P95/P99 lines
    - Total Requests by Method - summary table
    - Error Rate Over Time - failure rate graph
    - Current Success Rate - stat panel with thresholds
    - Average Latency (P95) - stat panel with performance thresholds
    - Total Requests (Last 24h) - volume indicator
  - `docs/grafana_setup.md`: Complete setup guide with import instructions, troubleshooting, and Docker Compose example
  - `docker-compose.yml`: Multi-container setup with Prometheus and Grafana
  - `prometheus.yml`: Prometheus configuration for metrics scraping
  - Visualizes `redox_requests_total` counter and `redox_request_duration_seconds` histogram
  - Demo mode implementation for generating test metrics
- **Artifacts:** dashboard.json file, setup documentation, Docker Compose configuration, import instructions, working demo
- **Why:** Visual demonstration of observability setup, resume-worthy deliverable showcasing Grafana/Prometheus expertise

## Tier B — Light Lifts, Great Credibility

### 5. SLOs + Basic Self-Healing
**Status:** 📋 **PLANNED**
- Define SLOs (e.g., P95 send latency, success-rate)
- Add simple retry budget metric
- Fail-open policy for known transient errors
- Dead-letter capture to file/queue
- **Artifacts:** docs/slo.md, metrics showing success/latency, retry-budget graph in Grafana

### 6. Containerization + One-Command Dev
**Status:** ✅ **COMPLETED** - Docker Compose setup for full observability stack
- Dockerfile + docker-compose.yml (service + Prometheus + Grafana)
- **Current Implementation:**
  - `docker-compose.yml`: Multi-container setup with FastAPI, Prometheus, and Grafana
  - `prometheus.yml`: Prometheus configuration for metrics scraping
  - One-command startup: `docker-compose up -d`
  - Integrated with Grafana dashboard for complete observability demo
- **Artifacts:** `docker-compose up` launches complete monitoring stack, README documentation for setup
- **Why:** Developer experience, demo capabilities, infrastructure as code

### 7. Security Doc Stub + Threat Model
**Status:** 📋 **PLANNED**
- docs/security.md: HIPAA controls (authN/Z, PHI redaction, audit, key mgmt)
- STRIDE mini-threat model for the integration gateway
- Secrets policy
- **Why:** HIPAA/SOC-2 understanding; threat modeling; security reviews

## Tier C — Bigger Moves (If Time Permits)

### 8. Message Bus
**Status:** 📋 **PLANNED**
- Redpanda (Kafka-compatible) dev container
- aiokafka producer/consumer that echoes outbound messages and DLQs failures
- **Why:** Kafka/RabbitMQ = A thin producer/consumer loop is enough

### 9. Kubernetes
**Status:** 📋 **PLANNED**
- Minimal k8s manifest (or Helm chart) for the service + Prometheus Operator scrape config
- **Why:** Demonstrates orchestration literacy without a big infra lift

---

## Implementation Notes

- **Tier A items** are prioritized as they provide maximum interview signal with minimal effort
- **Completed items** are moved to [FEATURES.md](FEATURES.md) with detailed implementation notes
- **Progress tracking** uses emoji status indicators:
  - ✅ **COMPLETED** - Fully implemented and tested
  - 🔄 **IN PROGRESS** - Currently being worked on
  - 📋 **PLANNED** - Planned but not started
  - 🔄 **ON HOLD** - Temporarily paused

## Current Focus

**All Tier A items completed!** 🎉

**Next Priority:** SLOs + Basic Self-Healing (Tier B #5)
- Define SLOs for P95 latency and success rates
- Implement retry budget metrics
- Add fail-open policies for transient errors
- Create dashboard.json with panels for Redox metrics
- Add screenshots to documentation
