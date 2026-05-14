# 审计 08：监控、日志与可观测性
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.ca.md)


**日期：** 2024-07-25
**分析师：** Jules

## 1. 发现摘要

| 状态 | 领域 | 发现摘要 |
| :--- | :--- | :--- |
| ✓ | **指标采集** | Prometheus 堆栈**配置良好**，可采集关键基础设施指标，包括宿主机指标 (`node-exporter`)、容器指标 (`cadvisor`) 以及专门的 GPU 指标 (`nvidia-dcgm-exporter`)。 |
| ✓ | **Grafana 配置自动化 (Provisioning)** | Grafana 配置的 GitOps 方法**非常出色**。Prometheus 数据源和仪表板均为自动配置，确保了一致性和可复现性。 |
| ⚠️ | **可见性受限** | 现有的仪表板几乎完全集中在 AI 服务指标（Ollama, GPU）上。**缺少针对整体系统和容器健康状况的关键仪表板**，这造成了重大的监控盲点。 |
| ✗ | **缺少告警系统** | Prometheus 配置**完全缺少 `alerting` 章节和 `rule_files`**。这意味着系统无法主动通知操作员有关服务故障、资源枯竭或异常行为的信息。监控纯粹是被动的。 |
| ✗ | **日志未集中化** | 不存在日志聚合系统（如 ELK/Loki 堆栈）。日志被写入 Docker 卷中的文件或标准输出 (`stdout`)。这使得跨不同服务的事件关联**极其困难且缓慢**，尤其是在事故调查期间。 |
| ✗ | **日志访问不安全** | 没有集中且安全的日志访问机制。为了查看日志，操作员需要直接访问 Docker 宿主机的文件系统，这是一种违反最小权限原则的不良安全实践。 |

---

## 2. 详细发现

### ✓ 优点

1.  **稳固的指标基础：**
    *   `prometheus.yml` 的配置非常稳健。它包含了针对 `node-exporter`（宿主机指标）、`cadvisor`（容器指标）、`nvidia-dcgm-exporter`（GPU 指标）以及用于应用端点健康检查的 `blackbox-exporter` 的 `scrape_configs`。这是可观测性的绝佳基础。

2.  **基础设施即代码 (IaC) 监控：**
    *   Grafana 通过 YAML 文件 (`grafana/provisioning`) 进行配置，这意味着数据源和仪表板配置已在 Git 中进行版本控制。这是一种现代且强烈推荐的做法，避免了手动配置和配置漂移。

### ✗ 发现的问题

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **M-01** | **关键** | **完全缺少告警** | 如果 `postgres` 或 `authelia` 等关键服务宕机，或者服务器磁盘写满，**没有人会收到通知**。故障只能在用户报告问题时才会被发现，这极大地增加了平均检测时间 (MTTD) 和平均修复时间 (MTTR)。 |
| **M-02** | **高** | **缺少日志聚合** | 在安全事件或连锁故障期间，能够跨多个服务查看按时间关联的事件序列至关重要。如果没有集中化的日志系统，这项任务将是手动的、缓慢的且容易出错，使得根本原因分析极其困难。 |
| **M-03** | **中** | **仪表板盲点** | 虽然有针对 Ollama 的仪表板，但没有仪表板用于可视化重要的宿主机指标（来自 `node-exporter` 的 CPU、内存、磁盘 I/O、网络使用情况）或整体容器健康状况（资源使用、重启、`cadvisor` 状态）。这阻碍了对性能或容量问题的积极检测。 |

---

### ⚠️ 警告/建议

1.  **指标保留策略：**
    *   Prometheus 配置的保留时间为 15 天 (`--storage.tsdb.retention.time=15d`)。对于长期趋势分析来说，这个时间较短。如果需要更长的历史记录，应考虑使用 Thanos 或 VictoriaMetrics 等长期存储解决方案。

2.  **Grafana 安全性：**
    *   Grafana 管理员凭据通过环境变量设置，这比硬编码要好。但是，默认密码是 `admin`。`docker-compose.yml` 应包含清晰的注释，指出此密码必须在首次登录后立即更改。

---

### 🔧 建议的解决方案

1.  **针对 M-01（实施告警）：**
    *   **解决方案：** 在监控堆栈中集成 `Alertmanager`。
        1.  **在 `docker-compose.yml` 中添加 `Alertmanager`：**
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
        2.  **创建 `prometheus/alertmanager.yml`：** 配置通知接收端（如邮件、Slack、Telegram）。
        3.  **更新 `prometheus.yml`：** 添加配置使 Prometheus 将告警发送到 Alertmanager 并加载规则文件。
            ```yaml
            # 在 prometheus.yml 中
            alerting:
              alertmanagers:
                - static_configs:
                    - targets: ['alertmanager:9093']

            rule_files:
              - "/etc/prometheus/alert-rules.yml"
            ```
        4.  **创建 `prometheus/alert-rules.yml`：** 定义关键告警规则（例如 `HostHighCpuLoad`, `ContainerDown`, `DiskSpaceLow`）。

2.  **针对 M-02（集中化日志）：**
    *   **解决方案：** 在堆栈中添加 `Loki` 和 `Promtail` 进行日志聚合。
        1.  **在 `docker-compose.yml` 中添加 `Loki` 和 `Promtail`：**
            ```yaml
            loki:
              image: grafana/loki:2.9.0
              # ... Loki 配置 ...
            promtail:
              image: grafana/promtail:2.9.0
              # ... 采集容器日志的 Promtail 配置 ...
            ```
        2.  **配置 Grafana：** 将 Loki 添加为新的数据源，以便能够在查看指标的同时探索和可视化日志。

3.  **针对 M-03（提高可见性）：**
    *   **解决方案：** 为 `node-exporter` 和 `cadvisor` 添加社区标准仪表板。
        *   从 [Grafana Marketplace](https://grafana.com/grafana/dashboards/) 下载热门仪表板的 JSON，例如 "Node Exporter Full" (ID 1860) 和 "Docker and System Monitoring" (ID 893)。
        *   将它们添加到 `grafana/dashboards/` 目录中，以便自动配置。
