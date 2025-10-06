# Grafana Dashboard Preview

Since you need Grafana to actually view the interactive dashboard, here are some options to see the dashboard in action:

## Option 1: Grafana Cloud (Free)
1. Go to [grafana.com](https://grafana.com) and sign up for a free account
2. Create a new dashboard
3. Import the `docs/grafana_dashboard.json` file
4. You'll need to connect it to a Prometheus data source (can use a demo one)

## Option 2: Local Docker Setup
Use this docker-compose.yml to run Grafana locally:

```yaml
version: '3.8'
services:
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

Run with: `docker-compose up -d`

## Option 3: View Dashboard Structure
The dashboard contains these panels:

### 📊 **Dashboard Layout Preview**

```
┌─────────────────────────────────────────────────────────────┐
│ Request Rate (per second)          │ Success Rate (%)       │
│ [Time Series Graph]                │ [Time Series Graph]    │
│ Shows RPS for each API method      │ Shows % success rate   │
├────────────────────────────────────┼─────────────────────────┤
│                                     │ Error Rate Over Time   │
│ Request Latency Percentiles         │ [Time Series Graph]    │
│ P50/P95/P99 lines for each method   │ Shows errors/sec       │
├────────────────────────────────────┼─────────────────────────┤
│ Total Requests by Method           │                         │
│ [Table]                            │                         │
│ Shows total counts per method      │                         │
├────────────────────────────────────┼─────────────────────────┤
│ Current Success Rate  │ Avg Latency (P95) │ Total (24h)     │
│ [Stat: 99.5%]         │ [Stat: 1.2s]      │ [Stat: 1,234]   │
│ Green/Yellow/Red      │ Green/Yellow/Red  │ Count indicator  │
└────────────────────────────────────┴─────────────────────────┘
```

### 🎨 **Color Thresholds**
- **Success Rate**: Green (>99%), Orange (95-99%), Red (<95%)
- **Latency**: Green (<2s), Orange (2-5s), Red (>5s)

### 📈 **Metrics Used**
- `redox_requests_total{method, status}` - Request counters
- `redox_request_duration_seconds{method}` - Latency histograms

## Quick Demo
If you want to see metrics without full setup, you can:
1. Start your FastAPI app: `uvicorn app.main:app --reload`
2. Visit `http://localhost:8000/health/metrics` to see raw Prometheus metrics
3. These are the same metrics that would feed into Grafana

The dashboard JSON file is ready to import - you just need a Grafana instance to visualize it!
