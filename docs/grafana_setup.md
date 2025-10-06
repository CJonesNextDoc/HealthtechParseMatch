# Grafana Dashboard Setup

This document explains how to set up Grafana to visualize the HealthtechParseMatch Redox API metrics.

## Prerequisites

- Grafana instance running (local or cloud)
- Prometheus data source configured in Grafana
- HealthtechParseMatch application running with metrics exposed

## Dashboard Import

1. **Open Grafana** and navigate to the Dashboards section
2. **Click "New" → "Import"**
3. **Upload the dashboard JSON file**: `docs/grafana_dashboard.json`
4. **Configure Data Source**: Select your Prometheus data source
5. **Click "Import"**

## Dashboard Panels

The dashboard includes the following panels:

### 1. Request Rate (per second)
- Shows the rate of requests per second for each Redox API method
- Uses `rate(redox_requests_total[5m])` query

### 2. Success Rate (%)
- Displays the percentage of successful requests for each method
- Formula: `rate(success_requests) / rate(total_requests) * 100`

### 3. Request Latency Percentiles
- Shows P50, P95, and P99 latency percentiles
- Uses histogram quantiles from `redox_request_duration_seconds`

### 4. Total Requests by Method
- Table showing total request counts grouped by method
- Uses `sum(redox_requests_total) by (method)`

### 5. Error Rate Over Time
- Time series showing error rates per second
- Uses `rate(redox_requests_total{status="failure"}[5m])`

### 6. Current Success Rate
- Stat panel showing overall success rate with color thresholds
- Green: >99%, Orange: 95-99%, Red: <95%

### 7. Average Latency (P95)
- Stat panel showing P95 latency with performance thresholds
- Green: <2s, Orange: 2-5s, Red: >5s

### 8. Total Requests (Last 24h)
- Shows total requests in the last 24 hours
- Uses `sum(increase(redox_requests_total[24h]))`

## Metrics Reference

The dashboard visualizes these Prometheus metrics:

- `redox_requests_total{method, status}` - Counter of total API requests
- `redox_request_duration_seconds{method}` - Histogram of request latencies

## Screenshots

![Grafana Dashboard Overview](grafana-dashboard-overview.png)

*Note: Add actual screenshots after setting up the dashboard*

## Troubleshooting

### No Data Showing
1. Verify Prometheus is scraping the HealthtechParseMatch metrics endpoint
2. Check that the `/health/metrics` endpoint is accessible
3. Ensure the Prometheus data source in Grafana is correctly configured

### Incorrect Data Source
- When importing, make sure to select the correct Prometheus data source
- You can change the data source later by editing the dashboard settings

### Performance Issues
- The dashboard queries use 5-minute rate calculations for smooth graphs
- Adjust the time range or query intervals if needed for your use case

## Docker Compose Setup (Optional)

For a complete local observability stack, you can use this docker-compose.yml:

```yaml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  grafana_data:
```

Configure Prometheus to scrape your HealthtechParseMatch app by adding to prometheus.yml:

```yaml
scrape_configs:
  - job_name: 'healthtech'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/health/metrics'
```
