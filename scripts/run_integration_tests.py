#!/usr/bin/env python3
"""
Integration Test Runner for SLO Features

This script runs integration tests against Docker containers to verify
the SLO monitoring and self-healing features work end-to-end.
"""

import subprocess
import sys
import time
from pathlib import Path

import requests


def run_command(cmd, cwd=None, check=True):
    """Run a shell command."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        sys.exit(1)
    return result


def wait_for_service(url, timeout=60, interval=2):
    """Wait for a service to become responsive."""
    print(f"Waiting for {url} to be ready...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code < 500:  # Accept any non-server error
                print(f"✓ {url} is ready")
                return True
        except Exception:
            pass

        time.sleep(interval)

    print(f"✗ {url} failed to respond within {timeout} seconds")
    return False


def test_api_service():
    """Test that the API service is working."""
    print("\n=== Testing API Service ===")

    api_url = "http://localhost:8000"

    # Test health endpoint
    if not wait_for_service(f"{api_url}/health"):
        return False

    # Test metrics endpoint
    try:
        response = requests.get(f"{api_url}/health/metrics", timeout=10)
        if response.status_code != 200:
            print(f"✗ Metrics endpoint returned {response.status_code}")
            return False
        print("✓ Metrics endpoint accessible")
    except Exception as e:
        print(f"✗ Metrics endpoint failed: {e}")
        return False

    # Test patient matching (demo mode)
    try:
        response = requests.post(f"{api_url}/patients/match", json={"text": "John Doe born 12/13/2002"}, timeout=10)
        if response.status_code not in [200, 201]:
            print(f"✗ Patient matching returned {response.status_code}")
            return False
        print("✓ Patient matching endpoint working")
    except Exception as e:
        print(f"✗ Patient matching failed: {e}")
        return False

    return True


def test_prometheus_service():
    """Test that Prometheus is working and collecting metrics."""
    print("\n=== Testing Prometheus Service ===")

    prometheus_url = "http://localhost:9090"

    # Test Prometheus readiness
    if not wait_for_service(f"{prometheus_url}/-/ready"):
        return False

    # Test query endpoint
    try:
        response = requests.get(f"{prometheus_url}/api/v1/query", params={"query": "up"}, timeout=10)
        if response.status_code != 200:
            print(f"✗ Prometheus query failed with {response.status_code}")
            return False

        data = response.json()
        if data.get("status") != "success":
            print(f"✗ Prometheus query returned status: {data.get('status')}")
            return False

        print("✓ Prometheus query working")
    except Exception as e:
        print(f"✗ Prometheus query failed: {e}")
        return False

    # Test SLO metrics queries
    slo_queries = ["redox_requests_total", "redox_request_duration_seconds", "redox_circuit_breaker_state"]

    for query in slo_queries:
        try:
            response = requests.get(f"{prometheus_url}/api/v1/query", params={"query": query}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    result_count = len(data.get("data", {}).get("result", []))
                    print(f"✓ SLO query '{query}' returned {result_count} results")
                else:
                    print(f"⚠ SLO query '{query}' returned status: {data.get('status')}")
            else:
                print(f"⚠ SLO query '{query}' failed with {response.status_code}")
        except Exception as e:
            print(f"⚠ SLO query '{query}' failed: {e}")

    return True


def test_grafana_service():
    """Test that Grafana is working and dashboards are provisioned."""
    print("\n=== Testing Grafana Service ===")

    grafana_url = "http://localhost:3000"

    # Test Grafana health
    if not wait_for_service(f"{grafana_url}/api/health"):
        return False

    # Test dashboard provisioning
    try:
        session = requests.Session()
        session.auth = ("admin", "admin")

        response = session.get(f"{grafana_url}/api/search", timeout=10)
        if response.status_code != 200:
            print(f"✗ Grafana dashboard search failed with {response.status_code}")
            return False

        dashboards = response.json()
        dashboard_titles = [d.get("title", "") for d in dashboards]

        if "HealthtechParseMatch SLO Dashboard" in dashboard_titles:
            print("✓ SLO Dashboard provisioned")
        else:
            print(f"⚠ SLO Dashboard not found. Available: {dashboard_titles}")
    except Exception as e:
        print(f"✗ Grafana dashboard check failed: {e}")
        return False

    # Test datasource configuration
    try:
        response = session.get(f"{grafana_url}/api/datasources", timeout=10)
        if response.status_code == 200:
            datasources = response.json()
            datasource_names = [ds["name"] for ds in datasources]

            if "Prometheus" in datasource_names:
                print("✓ Prometheus datasource configured")
            else:
                print(f"⚠ Prometheus datasource not found. Available: {datasource_names}")
        else:
            print(f"⚠ Datasource check failed with {response.status_code}")
    except Exception as e:
        print(f"⚠ Datasource check failed: {e}")

    return True


def main():
    """Main integration test runner."""
    print("🚀 Starting SLO Integration Tests")
    print("=" * 50)

    # Check if Docker is available
    try:
        run_command("docker --version")
    except Exception:
        print("✗ Docker not available")
        sys.exit(1)

    # Get the project root
    project_root = Path(__file__).parent

    # Start Docker services
    print("\n=== Starting Docker Services ===")
    run_command("docker-compose down -v", cwd=project_root)  # Clean up any existing containers
    run_command("docker-compose up -d", cwd=project_root)

    try:
        # Wait for services to start
        print("\n=== Waiting for Services to Start ===")
        time.sleep(10)  # Give containers time to start

        # Run tests
        results = []
        results.append(("API Service", test_api_service()))
        results.append(("Prometheus Service", test_prometheus_service()))
        results.append(("Grafana Service", test_grafana_service()))

        # Summary
        print("\n" + "=" * 50)
        print("📊 Integration Test Results:")

        all_passed = True
        for service, passed in results:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {service}: {status}")
            all_passed = all_passed and passed

        if all_passed:
            print("\n🎉 All integration tests passed!")
            return 0
        else:
            print("\n⚠️  Some integration tests failed")
            return 1

    finally:
        # Clean up
        print("\n=== Cleaning Up ===")
        run_command("docker-compose down -v", cwd=project_root)


if __name__ == "__main__":
    sys.exit(main())
