# connect-core **(cognito-stack)** 🚀
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/README.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/README.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/README.ca.md)


[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-3.8+-2496ED?logo=docker)](https://docs.docker.com/compose/)
[![n8n](https://img.shields.io/badge/n8n-1.121.0-red)](https://n8n.io/)
[![Status](https://img.shields.io/badge/Status-活跃-brightgreen)](https://github.com/Axlfc/connect-core)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?logo=node.js)](https://nodejs.org/)

**connect-code** - **cognito-stack** 是一个模块化的容器化 AI 编排平台，它将工作流自动化、图像生成和本地人工智能集成到单个可重现且可扩展的 Docker Compose 堆栈中。它支持多个容器运行时（Docker 和 Podman）和硬件配置文件（CPU、NVIDIA GPU、AMD GPU）。

> ⚠️ **安全警告：** 该项目正在积极开发中，在没有进行彻底安全审计的情况下，不应部署在生产环境中。

## 📋 目录

- [描述](#描述)
- [变体版本](#-变体版本)
- [主要特征](#-主要特征)
- [解决的问题](#-解决的问题)
- [使用案例](#-使用案例)
- [项目结构](#-项目结构)
- [先决条件](#-先决条件)
- [Docker 安装](#-docker-安装)
- [容器运行时](#-容器运行时) ⭐ **新：支持 Podman**
- [多架构兼容性矩阵](#-多架构兼容性矩阵) ⭐ **新：Apple Silicon**
- [项目安装](#-项目安装)
- [配置](#-配置)
- [使用](#-使用)
- [语音服务](#-语音服务)
- [架构](#-架构)
- [使用的技术](#-使用的技术)
- [API 和集成点](#-API-和集成点)
- [CI/CD 流水线](#-CI/CD-流水线)
- [故障排除](#-故障排除)
- [贡献](#-贡献)
- [许可证](#-许可证)
- [联系方式](#-联系方式)

---

## 描述

**cognito-stack** 是一个企业级解决方案，用于编排人工智能和自动化流水线，而无需依赖付费的外部 API 或失去对数据的控制。它结合了行业领先的开源工具，采用了高度可定制的容器化架构，可以在任何安装了 Docker 的机器上运行。

该平台专为需要以下内容的开发人员、数据科学家和 AI 团队设计：
- **可重现性**：在任何机器上都有相同的环境
- **隐私性**：模型和数据保留在本地
- **可扩展性**：带有外部运行器的模块化架构
- **灵活性**：异构组件的集成

---

## 🔄 变体版本

- [**simplified-stack**](simplified-stack/README.zh-cn.md): 为本地开发优化的轻量级版本，集成了 Drupal、Obsidian 和 Forgejo，用于隔离的 AI 工作流。
- [**very-simplified-stack**](very-simplified-stack/README.zh-cn.md): 删除了 n8n 编排的极简版本，专注于语音服务和 Cognito 代理 API，旨在连接到外部 Ollama 实例。

---

## ✨ 主要特征

- **n8n 工作流自动化** (端口 5678)
  - 用于创建复杂工作流的可视化界面
  - 外部任务运行器系统 (JavaScript + Python)
  - 自定义代码的隔离执行

- **本地 LLMs (Ollama)** (端口 11434)
  - 支持 CPU 和 GPU (NVIDIA/AMD)
  - 预加载模型：Llama 3.2, Qwen, Deepseek-R1 等
  - 无外部 API 依赖

- **ComfyUI 图像生成** (端口 8188)
  - 集成 Stable Diffusion
  - 优化的 NVIDIA GPU 支持
  - 批量图像处理

- **Matrix Synapse 协作和消息传递** (端口 8008)
  - 联合聊天服务器
  - 专用 PostgreSQL 数据库
  - 会话集成 Redis

- **Qdrant 向量数据库** (端口 6333)
  - 嵌入存储
  - RAG 的语义搜索
  - 数据持久性

- **Zrok 安全远程访问**
  - 安全的 webhook 隧道
  - n8n 的公共 URL
  - 无需在互联网上公开端口

---

## 🛡️ 安全

该堆栈包括使用 **Fail2ban** 防范暴力破解和 DoS 攻击。

- **受保护的服务：** n8n, Forgejo, Matrix Synapse。
- **机制：** 实时监控日志并阻止显示可疑行为（如多次登录尝试失败）的恶意 IP。
- **配置：** 规则位于 `fail2ban/` 目录中。默认情况下，IP 在 5 次尝试失败后将被锁定一小时。

---

## 🤝 贡献

我们非常欢迎您的贡献。请：

1. **Fork** 仓库
2. **创建分支** (`git checkout -b feature/AmazingFeature`)
3. **提交更改** (`git commit -m 'Add AmazingFeature'`)
4. **推送到分支** (`git push origin feature/AmazingFeature`)
5. **开启 Pull Request**

更多详情，请参见 [CONTRIBUTING.zh-cn.md](CONTRIBUTING.zh-cn.md)

---

## 📄 许可证

该项目根据 **GNU Affero General Public License v3 (AGPL-3.0)** 获得许可。

- ✅ 您可以运行、修改和分发
- ✅ 您必须包含更改通知
- ✅ 如果您通过网络运行，则必须共享源代码
- 📖 [查看完整许可证](LICENSE.zh-cn.md)

---

<div align="center">

**由 cognito-stack 团队精心打造 ❤️**

⭐ 如果你觉得它有用，请给它一颗星！

</div>
