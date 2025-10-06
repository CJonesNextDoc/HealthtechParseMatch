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
**Status:** 📋 **PLANNED**
- Create Grafana dashboard JSON for Redox metrics
- Include panels for request rates, latency percentiles, success rates
- Add screenshots to documentation
- **Why:** Visual demonstration of observability setup, resume-worthy deliverable
- **Artifacts:** dashboard.json file, screenshots in docs/, Grafana import instructions

## Tier B — Light Lifts, Great Credibility

### 5. SLOs + Basic Self-Healing
**Status:** 📋 **PLANNED**
- Define SLOs (e.g., P95 send latency, success-rate)
- Add simple retry budget metric
- Fail-open policy for known transient errors
- Dead-letter capture to file/queue
- **Artifacts:** docs/slo.md, metrics showing success/latency, retry-budget graph in Grafana

### 6. Containerization + One-Command Dev
**Status:** 📋 **PLANNED**
- Dockerfile + docker-compose.yml (service + Prometheus + Grafana)
- **Artifacts:** `make up`, `make down` or `docker compose up` to demo the whole mini-stack

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

**Next Priority:** Complete Partner Onboarding Starter Kit (Tier A #3)
- Create docs/partners.md
- Export Postman collection
- Build simple SDK wrapper

**Then:** Grafana Dashboard for Metrics Visualization (Tier A #4)
- Create dashboard.json with panels for Redox metrics
- Add screenshots to documentation
