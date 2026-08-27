# Prometheus & Grafana Integration Guide for Cognito Backend

This guide describes how to connect the `cognito-backend` `/metrics` endpoint to an existing Prometheus server and Grafana monitoring setup.

## Endpoint Overview

`cognito-backend` exposes a `/metrics` HTTP GET endpoint in standard Prometheus exposition format (`text/plain; version=0.0.4; charset=utf-8`).

- **Endpoint URL**: `http://<cognito-backend-host>:8000/metrics`
- **Authentication**: None required (or protected via ingress/mesh policies)

## Key Metrics Exposed

| Metric Name | Type | Description | Key Labels |
|---|---|---|---|
| `cognito_operation_duration_seconds` | Histogram | Execution time of backend operations in seconds | `operation`, `trace_id` |
| `cognito_tool_failures_total` | Counter | Total failure count during tool executions | `tool_name`, `trace_id` |
| `cognito_retries_total` | Counter | Total retries performed by backend operations | `operation`, `trace_id` |
| `cognito_tokens_total` | Counter | Total AI tokens consumed per user/model | `user_id`, `model`, `token_type` (`prompt`/`completion`), `trace_id` |
| `cognito_cost_dollars_total` | Counter | Total estimated cost in USD per user/model | `user_id`, `model`, `trace_id` |

### Trace Cross-Referencing (AUD-025 Integration)
Where applicable, metrics include `trace_id="<id>"`. This allows operators in Grafana to jump directly from metric spikes or anomalies to corresponding log entries in Loki or OpenSearch using `trace_id`.

---

## 1. Prometheus Configuration

Add a scrape job to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'cognito-backend'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['cognito-backend:8000']
```

Restart or reload Prometheus configuration:
```bash
curl -X POST http://localhost:9090/-/reload
```

---

## 2. Grafana Dashboard Queries

### Token Consumption per User
```promql
sum(rate(cognito_tokens_total[5m])) by (user_id, model, token_type)
```

### Estimated Cost per User (USD)
```promql
sum(increase(cognito_cost_dollars_total[1h])) by (user_id, model)
```

### Tool Execution Failure Rate
```promql
sum(rate(cognito_tool_failures_total[5m])) by (tool_name)
```

### Operational Latency (p95)
```promql
histogram_quantile(0.95, sum(rate(cognito_operation_duration_seconds_bucket[5m])) by (le, operation))
```

### Retries Rate
```promql
sum(rate(cognito_retries_total[5m])) by (operation)
```
