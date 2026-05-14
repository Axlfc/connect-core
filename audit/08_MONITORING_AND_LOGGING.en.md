# AUDIT 08: MONITORING, LOGGING, AND OBSERVABILITY
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✓ | **Metrics Collection** | The Prometheus stack is **well-configured** to collect key infrastructure metrics, including host metrics (`node-exporter`), container metrics (`cadvisor`), and specialized GPU metrics (`nvidia-dcgm-exporter`). |
| ✓ | **Grafana Provisioning** | The GitOps approach for Grafana configuration is **excellent**. Both the Prometheus data source and the dashboards are automatically provisioned, ensuring consistency and reproducibility. |
| ⚠️ | **Limited Visibility** | Existing dashboards focus almost exclusively on AI service metrics (Ollama, GPU). **Crucial dashboards are missing** for overall system and container health, creating significant blind spots. |
| ✗ | **No Alerting System** | The Prometheus configuration **completely lacks an `alerting` section and `rule_files`**. This means the system cannot proactively notify operators about service failures, resource exhaustion, or anomalous behavior. Monitoring is purely passive. |
| ✗ | **Non-Centralized Logging** | No log aggregation system exists (like the ELK/Loki stack). Logs are written to files within Docker volumes or to standard output (`stdout`). This makes correlating events between different services **extremely difficult and slow**, especially during incident investigation. |
| ✗ | **Insecure Log Access** | There is no centralized and secure mechanism for accessing logs. To review logs, an operator would need direct access to the Docker host's filesystem, which is a poor security practice that violates the principle of least privilege. |

---

## 2. Detailed Findings

### ✓ What is right

1.  **Solid Metrics Base:**
    *   The `prometheus.yml` configuration is robust. It includes `scrape_configs` for `node-exporter` (host metrics), `cadvisor` (container metrics), `nvidia-dcgm-exporter` (GPU metrics), and `blackbox-exporter` for application endpoint health checks. This is an excellent base for observability.

2.  **Infrastructure as Code (IaC) for Monitoring:**
    *   Grafana is provisioned via YAML files (`grafana/provisioning`), meaning data source and dashboard configuration is versioned in Git. This is a modern and highly recommended practice that avoids manual configuration and configuration drift.

### ✗ Problems Found

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **M-01** | **CRITICAL** | **Total Absence of Alerts** | If a critical service like `postgres` or `authelia` goes down, or if the server disk fills up, **no one will be notified**. The failure will only be discovered when users report problems, drastically increasing Mean Time to Detection (MTTD) and Mean Time to Resolution (MTTR). |
| **M-02** | **HIGH** | **Lack of Log Aggregation** | During a security incident or cascading failure, it is crucial to be able to see a sequence of events correlated in time across multiple services. Without a centralized logging system, this task is manual, slow, and error-prone, making root cause analysis extremely difficult. |
| **M-03** | **MEDIUM** | **Dashboard Blind Spots** | While dashboards exist for Ollama, there are none for visualizing vital host metrics (CPU, memory, disk I/O, network use from `node-exporter`) or overall container health (resource use, restarts, `cadvisor` status). This prevents proactive detection of performance or capacity issues. |

### ⚠️ Warnings/Recommendations

1.  **Metrics Retention:**
    *   Prometheus is configured with a 15-day retention (`--storage.tsdb.retention.time=15d`). This is low for long-term trend analysis. Using a long-term storage solution like Thanos or VictoriaMetrics should be considered if more history is needed.

2.  **Grafana Security:**
    *   Grafana administrator credentials are set via environment variables, which is better than hardcoding. However, the default password is `admin`. `docker-compose.yml` should include a clear comment stating that this password must be changed immediately after the first login.

### 🔧 Suggested Solutions

1.  **For M-01 (Implement Alerting):**
    *   **Solution:** Integrate `Alertmanager` into the monitoring stack.
        1.  **Add `Alertmanager` to `docker-compose.yml`:**
            ```yaml
            alertmanager:
              image: prom/alertmanager:v0.27.0
              container_name: alertmanager
              networks: [monitoring]
              restart: unless-stopped
              volumes:
                - ./prometheus/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
              ports:
                - "9093:9093"
            ```
        2.  **Create `prometheus/alertmanager.yml`:** Configure notification receivers (e.g., Email, Slack, Telegram).
        3.  **Update `prometheus.yml`:** Add configuration for Prometheus to send alerts to Alertmanager and load rule files.
            ```yaml
            # In prometheus.yml
            alerting:
              alertmanagers:
                - static_configs:
                    - targets: ['alertmanager:9093']

            rule_files:
              - "/etc/prometheus/alert-rules.yml"
            ```
        4.  **Create `prometheus/alert-rules.yml`:** Define critical alert rules (e.g., `HostHighCpuLoad`, `ContainerDown`, `DiskSpaceLow`).

2.  **For M-02 (Centralize Logs):**
    *   **Solution:** Add `Loki` and `Promtail` to the stack for log aggregation.
        1.  **Add `Loki` and `Promtail` to `docker-compose.yml`:**
            ```yaml
            loki:
              image: grafana/loki:2.9.0
              # ... Loki configuration ...
            promtail:
              image: grafana/promtail:2.9.0
              # ... Promtail configuration to collect container logs ...
            ```
        2.  **Configure Grafana:** Add Loki as a new data source to be able to explore and visualize logs alongside metrics.

3.  **For M-03 (Improve Visibility):**
    *   **Solution:** Add standard community dashboards for `node-exporter` and `cadvisor`.
        *   Download JSONs for popular dashboards from the [Grafana Marketplace](https://grafana.com/grafana/dashboards/), such as "Node Exporter Full" (ID 1860) and "Docker and System Monitoring" (ID 893).
        *   Add them to the `grafana/dashboards/` directory for automatic provisioning.
