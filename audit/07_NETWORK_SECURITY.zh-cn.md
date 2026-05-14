# 审计 07：网络安全与防火墙
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.ca.md)


**日期：** 2024-07-25
**分析师：** Jules

## 1. 发现摘要

| 状态 | 领域 | 发现摘要 |
| :--- | :--- | :--- |
| ✓ | **内部网络分段** | Docker Compose 网络架构**设计得非常出色**，使用 `internal` 网络隔离后端服务，限制了内部攻击面。 |
| ⚠️ | **`fail2ban` 配置** | 已实施 `fail2ban` 服务，表明了防御暴力破解攻击的意图。然而，其配置**过于简单**，仅通过 Nginx 日志监控登录失败尝试。 |
| ✗ | **`fail2ban` 使用 `network_mode: host`** | 这是一个**关键的安全设计缺陷**。在宿主机网络模式下运行 `fail2ban` 破坏了容器隔离，赋予了其对宿主机系统网络接口的无限制访问权限。该容器一旦被攻破，可能会危及整个宿主机网络。 |
| ✗ | **缺少出口 (Egress) 控制** | 没有限制容器外发流量的网络策略。如果一个容器被攻破，它可能被用来下载恶意软件、连接到命令与控制 (C2) 服务器，或者不受限制地攻击互联网上的其他系统。 |
| ✗ | **不必要的端口暴露** | 多个服务直接向宿主机接口暴露端口（例如：`postgres` 在 `127.0.0.1:5432`，`whisper-stt` 在 `0.0.0.0:9001`）。在微服务架构中，通信应主要通过 Docker 内部网络进行，只有反向代理才应向外暴露端口。 |

---

## 2. 详细发现

### ✓ 优点

1.  **按网络进行服务隔离：**
    *   创建独立的网络（`frontend`, `backend`, `ai`, `monitoring`）并对不需要外部访问的网络使用 `internal: true`，这是在网络层面正确实现最小权限原则。这防止了后端被攻破的服务（如数据库）被外部直接访问。

### ✗ 发现的问题

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **N-01** | **关键** | **`fail2ban` 使用 `network_mode: host`** | `fail2ban` 容器使 Docker 网络隔离失效。它可以监控、干扰和操纵宿主机网络流量。攻破此容器的攻击者可以绕过主防火墙，攻击未公开暴露的宿主机服务，并在宿主机网络中获得持久立足点。 |
| **N-02** | **高** | **`fail2ban` 过滤器不足** | 当前配置仅封禁在特定登录端点产生 401 错误的 IP。它无法防御广泛的常见攻击，如目录扫描、SQL 注入、XSS 或应用层（第 7 层）拒绝服务攻击。这提供了一种虚假的安全感。 |
| **N-03** | **中** | **后端端口直接暴露** | `postgres` 和 `redis` 等服务向宿主机的 `127.0.0.1` 暴露端口。虽然这无法从公网访问，但允许运行在同一宿主机上的任何其他进程（包括其他配置错误的容器）尝试直接连接数据库或缓存，绕过应用层。 |
| **N-04** | **中** | **缺少出口流量控制 (Egress)** | 容器可以发起指向互联网任何目的地的外发连接。如果攻击者成功在容器（如 `ollama`）中执行代码，他们可以利用它下载黑客工具、将数据外传到外部服务器或加入僵尸网络。 |

### ⚠️ 警告/建议

1.  **内部流量可见性：**
    *   同一 Docker 网络中容器间的流量未加密 (TLS)。对于极高安全要求的环境（如 PCI DSS 合规性），可以考虑实施服务网格 (Service Mesh，如 Istio 或 Linkerd) 以强制对所有内部流量进行加密 (mTLS)。

### 🔧 建议的解决方案

1.  **针对 N-01 和 N-02（重新设计 `fail2ban` 策略）：**
    *   **理想方案（推荐）：** 移除 `fail2ban` 容器。**直接在宿主机操作系统上**安装并配置 `fail2ban`。这使其能够在不破坏 Docker 安全模型的情况下，合法且安全地访问宿主机日志和 `iptables`。
    *   **替代方案（如果必须留在容器中）：**
        1.  移除 `network_mode: host`。
        2.  添加 `NET_ADMIN` 和 `NET_RAW` 能力以允许操纵 `iptables`。
        3.  将宿主机的 `iptables` 日志文件挂载到容器内，以便其查看自身行为。
        4.  大规模扩展 `filter.d` 中的过滤器，包含 `nginx-badbots`, `nginx-noscript`, `nginx-http-auth` 以及其他预定义的 `fail2ban` 规则，以提供更全面的保护。

2.  **针对 N-03（限制端口暴露）：**
    *   **解决方案：** 审查 `docker-compose.yml` 中的每个服务，移除任何非外部访问（由 `nginx-proxy` 管理）或本地调试所必需的 `ports` 映射。服务间通信应通过 Docker 网络，使用服务名称作为 DNS（例如：`postgres:5432`）进行。
        ```diff
        --- a/docker-compose.yml
        +++ b/docker-compose.yml
        @@ -140,8 +140,6 @@
         hostname: postgres
         container_name: postgres
         networks:
           - backend
         restart: unless-stopped
-        ports:
-          - "127.0.0.1:5432:5432"
         secrets:
           - postgres_password
           - postgres_user
        ```

3.  **针对 N-04（出口控制）：**
    *   **解决方案：** 创建一个专门用于访问互联网的 Docker 网络，并仅连接到显式需要该功能的容器。
        1.  **在 `docker-compose.yml` 中定义出口网络：**
            ```yaml
            networks:
              egress_allowed:
                driver: bridge
            ```
        2.  **修改宿主机防火墙 (iptables)：** 添加规则，仅允许来自 `egress_allowed` 网络子网的 `FORWARD` 流量出站，并拒绝来自其他 Docker 网络的 `FORWARD` 流量。
            ```bash
            # iptables 规则示例（需要正确的子网）
            DOCKER_EGRESS_NW="172.x.y.0/24" # egress_allowed 网络的子网
            iptables -A FORWARD -i br-$(docker network ls | grep egress_allowed | awk '{print $1}') -o <external_iface> -j ACCEPT
            iptables -A FORWARD -i docker0 -o <external_iface> -j DROP
            ```
        3.  **将容器连接到该网络：** 仅将需要访问互联网的容器（如用于 webhooks 的 `n8n`）添加到 `egress_allowed` 网络中。
