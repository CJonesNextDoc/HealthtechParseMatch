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
- **Artifacts:** `/metrics` endpoint ready, Grafana dashboard JSON + screenshots (pending)
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
**Status:** 🔄 **IN PROGRESS**
- docs/partners.md (how to auth, send PatientAdmin, read FHIR)
- Postman collection for API testing
- 30-line Python SDK wrapper (pip install -e .)
- **Next Steps:**
  - Create docs/partners.md with authentication guide
  - Export Postman collection for Redox endpoints
  - Create simple SDK wrapper in separate package

## Tier B — Light Lifts, Great Credibility

### 4. SLOs + Basic Self-Healing
**Status:** 📋 **PLANNED**
- Define SLOs (e.g., P95 send latency, success-rate)
- Add simple retry budget metric
- Fail-open policy for known transient errors
- Dead-letter capture to file/queue
- **Artifacts:** docs/slo.md, metrics showing success/latency, retry-budget graph in Grafana

### 5. Containerization + One-Command Dev
**Status:** 📋 **PLANNED**
- Dockerfile + docker-compose.yml (service + Prometheus + Grafana)
- **Artifacts:** `make up`, `make down` or `docker compose up` to demo the whole mini-stack

### 6. Security Doc Stub + Threat Model
**Status:** 📋 **PLANNED**
- docs/security.md: HIPAA controls (authN/Z, PHI redaction, audit, key mgmt)
- STRIDE mini-threat model for the integration gateway
- Secrets policy
- **Why:** HIPAA/SOC-2 understanding; threat modeling; security reviews

## Tier C — Bigger Moves (If Time Permits)

### 7. Message Bus
**Status:** 📋 **PLANNED**
- Redpanda (Kafka-compatible) dev container
- aiokafka producer/consumer that echoes outbound messages and DLQs failures
- **Why:** Kafka/RabbitMQ = A thin producer/consumer loop is enough

### 8. Kubernetes
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
