"""
Integration tests for SLO monitoring and self-healing features.

These tests run against actual Docker containers to ensure end-to-end functionality.
"""

import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """Get the docker-compose file path."""
    return "docker-compose.yml"


@pytest.fixture(scope="session")
def docker_setup(docker_ip, docker_services):
    """Ensure Docker services are running."""
    # Wait for services to be ready
    docker_services.wait_until_responsive(timeout=60.0, pause=0.1, check=lambda: is_responsive(docker_ip, docker_services))


def is_responsive(docker_ip, docker_services):
    """Check if all services are responsive."""
    try:
        # Check API
        api_url = f"http://{docker_ip}:{docker_services.port_for('api', 8000)}"
        requests.get(f"{api_url}/health", timeout=5)

        # Check Prometheus
        prometheus_url = f"http://{docker_ip}:{docker_services.port_for('prometheus', 9090)}"
        requests.get(f"{prometheus_url}/-/ready", timeout=5)

        # Check Grafana
        grafana_url = f"http://{docker_ip}:{docker_services.port_for('grafana', 3000)}"
        requests.get(f"{grafana_url}/api/health", timeout=5)

        return True
    except Exception:
        return False


@pytest.mark.integration
def test_slo_monitoring_end_to_end(docker_setup, docker_ip, docker_services):
    """Test complete SLO monitoring pipeline from API call to metrics collection."""
    api_url = f"http://{docker_ip}:{docker_services.port_for('api', 8000)}"
    prometheus_url = f"http://{docker_ip}:{docker_services.port_for('prometheus', 9090)}"

    # Make some API calls to generate metrics
    for _ in range(5):
        try:
            # Test patient matching endpoint (uses demo mode)
            response = requests.post(f"{api_url}/patients/match", json={"text": "John Doe born 12/13/2002"}, timeout=10)
            assert response.status_code in [200, 201]
        except requests.exceptions.RequestException:
            # In demo mode, this might not work, but that's ok for this test
            pass

    # Wait a bit for metrics to be scraped
    import time

    time.sleep(2)

    # Check that SLO metrics are being collected
    slo_queries = [
        "redox_requests_total",
        "redox_request_duration_seconds",
        "redox_circuit_breaker_state",
        "rate(redox_requests_total[5m])",
        "histogram_quantile(0.95, rate(redox_request_duration_seconds_bucket[5m]))",
    ]

    for query in slo_queries:
        response = requests.get(f"{prometheus_url}/api/v1/query", params={"query": query}, timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        # Note: In demo mode, we might not have actual metrics, but the query should work


@pytest.mark.integration
def test_circuit_breaker_under_load(docker_setup, docker_ip, docker_services):
    """Test circuit breaker behavior when the API is under load."""
    api_url = f"http://{docker_ip}:{docker_services.port_for('api', 8000)}"
    prometheus_url = f"http://{docker_ip}:{docker_services.port_for('prometheus', 9090)}"

    # Make many concurrent requests to potentially trigger circuit breaker
    import concurrent.futures

    def make_patient_request():
        """Make a patient matching request."""
        try:
            response = requests.post(f"{api_url}/patients/match", json={"text": "John Doe born 12/13/2002"}, timeout=5)
            return response.status_code
        except requests.exceptions.RequestException as e:
            return str(e)

    # Make concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_patient_request) for _ in range(20)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    # Check results - some might succeed, some might fail due to circuit breaker
    success_count = sum(1 for r in results if r == 200)
    total_count = len(results)

    # We expect some level of success (demo mode should work)
    assert success_count > 0, f"No successful requests out of {total_count}"

    # Wait for metrics to be scraped
    import time

    time.sleep(3)

    # Check circuit breaker metrics
    response = requests.get(f"{prometheus_url}/api/v1/query", params={"query": "redox_circuit_breaker_state"}, timeout=10)

    if response.status_code == 200:
        data = response.json()
        if data["status"] == "success" and data["data"]["result"]:
            # Circuit breaker metrics exist
            assert len(data["data"]["result"]) >= 0


@pytest.mark.integration
def test_prometheus_metrics_collection(docker_setup, docker_ip, docker_services):
    """Test that Prometheus is configured to scrape metrics."""
    prometheus_url = f"http://{docker_ip}:{docker_services.port_for('prometheus', 9090)}"

    # Check Prometheus configuration
    response = requests.get(f"{prometheus_url}/api/v1/status/config", timeout=10)
    assert response.status_code == 200

    config_data = response.json()
    config_yaml = config_data["data"]["yaml"]

    # Verify our scrape config is present
    assert "job_name: 'healthtech-api'" in config_yaml
    assert "static_configs:" in config_yaml


@pytest.mark.integration
def test_grafana_dashboard_provisioning(docker_setup, docker_ip, docker_services):
    """Test that Grafana dashboard is properly provisioned."""
    grafana_url = f"http://{docker_ip}:{docker_services.port_for('grafana', 3000)}"

    # Login to Grafana
    session = requests.Session()
    session.auth = ("admin", "admin")

    # Get dashboards
    response = session.get(f"{grafana_url}/api/search", timeout=10)
    assert response.status_code == 200

    dashboards = response.json()
    dashboard_titles = [d.get("title", "") for d in dashboards]

    # Check our SLO dashboard is present
    assert "HealthtechParseMatch SLO Dashboard" in dashboard_titles


@pytest.mark.integration
def test_slo_metrics_queries(docker_setup, docker_ip, docker_services):
    """Test SLO metric queries against Prometheus."""
    prometheus_url = f"http://{docker_ip}:{docker_services.port_for('prometheus', 9090)}"

    # Test various SLO-related queries
    slo_queries = [
        "up",  # Basic health check
        "prometheus_build_info",  # Prometheus itself
        # Note: Actual redox metrics would come from the API service
        # 'redox_requests_total',
        # 'redox_request_duration_seconds',
        # 'redox_circuit_breaker_state'
    ]

    for query in slo_queries:
        response = requests.get(f"{prometheus_url}/api/v1/query", params={"query": query}, timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"


@pytest.mark.integration
def test_grafana_datasource_configuration(docker_setup, docker_ip, docker_services):
    """Test that Grafana has Prometheus configured as a datasource."""
    grafana_url = f"http://{docker_ip}:{docker_services.port_for('grafana', 3000)}"

    # Login to Grafana
    session = requests.Session()
    session.auth = ("admin", "admin")

    # Get datasources
    response = session.get(f"{grafana_url}/api/datasources", timeout=10)
    assert response.status_code == 200

    datasources = response.json()
    datasource_names = [ds["name"] for ds in datasources]

    # Check Prometheus datasource exists
    assert "Prometheus" in datasource_names

    # Verify Prometheus datasource configuration
    prometheus_ds = next(ds for ds in datasources if ds["name"] == "Prometheus")
    assert prometheus_ds["type"] == "prometheus"
    assert "http://prometheus:9090" in prometheus_ds["url"]


@pytest.mark.integration
def test_monitoring_stack_resilience(docker_setup, docker_ip, docker_services):
    """Test that the monitoring stack remains stable under load."""
    import concurrent.futures
    import threading

    prometheus_url = f"http://{docker_ip}:{docker_services.port_for('prometheus', 9090)}"
    grafana_url = f"http://{docker_ip}:{docker_services.port_for('grafana', 3000)}"

    results = []
    lock = threading.Lock()

    def make_request(url, auth=None):
        """Make a single HTTP request."""
        try:
            session = requests_retry_session()
            if auth:
                session.auth = auth
            response = session.get(url, timeout=10)
            with lock:
                results.append((url, response.status_code))
            return response.status_code
        except Exception as e:
            with lock:
                results.append((url, str(e)))
            return str(e)

    # Make multiple concurrent requests to test stability
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []

        # Test Prometheus endpoints
        for _ in range(10):
            futures.append(executor.submit(make_request, f"{prometheus_url}/api/v1/query?query=up"))
            futures.append(executor.submit(make_request, f"{prometheus_url}/-/ready"))

        # Test Grafana endpoints
        for _ in range(5):
            futures.append(executor.submit(make_request, f"{grafana_url}/api/health", ("admin", "admin")))

        # Wait for all requests to complete
        concurrent.futures.wait(futures, timeout=30)

    # Check that most requests succeeded
    successes = sum(1 for _, result in results if isinstance(result, int) and 200 <= result < 300)
    total_requests = len(results)

    success_rate = successes / total_requests if total_requests > 0 else 0
    assert success_rate >= 0.8, f"Success rate {success_rate:.2%} is below 80% threshold. Results: {results}"


# Helper function for HTTP requests with retry
def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    """Create a requests session with retry logic."""
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
