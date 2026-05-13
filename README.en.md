# cognito-stack 🚀
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/README.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/README.zh-cn.md)


[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-3.8+-2496ED?logo=docker)](https://docs.docker.com/compose/)
[![n8n](https://img.shields.io/badge/n8n-1.121.0-red)](https://n8n.io/)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen)](https://github.com/Axlfc/connect-core)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?logo=node.js)](https://nodejs.org/)

**cognito-stack** is a modular containerized AI orchestration platform that integrates workflow automation, image generation, and local artificial intelligence into a single reproducible and scalable Docker Compose stack. It supports multiple container runtimes (Docker and Podman) and hardware profiles (CPU, NVIDIA GPU, AMD GPU).

> ⚠️ **Security Warning:** This project is under active development and should not be deployed in a production environment without a thorough security audit.

## 📋 Table of Contents

- [Description](#description)
- [Variants](#-variants)
- [Main Features](#-main-features)
- [Problem it Solves](#-problem-it-solves)
- [Use Cases](#-use-cases)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Docker Installation](#-docker-installation)
- [Container Runtimes](#-container-runtimes) ⭐ **New: Podman Support**
- [Multi-Architecture Compatibility Matrix](#-multi-architecture-compatibility-matrix) ⭐ **New: Apple Silicon**
- [Project Installation](#-project-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Voice Services](#-voice-services)
- [Architecture](#-architecture)
- [Technologies Used](#-technologies-used)
- [API and Integration Points](#-api-and-integration-points)
- [CI/CD Pipeline](#-cicd-pipeline)
- [Troubleshooting](#-troubleshooting)
- [Contribution](#-contribution)
- [License](#-license)
- [Contact](#-contact)

---

## Description

**cognito-stack** is an enterprise solution for orchestrating artificial intelligence and automation pipelines without depending on paid external APIs or losing control of data. It combines industry-leading open-source tools in a highly customizable containerized architecture that can run on any machine with Docker.

The platform is designed for developers, data scientists, and AI teams that need:
- **Reproducibility**: Identical environment on any machine
- **Privacy**: Models and data remain local
- **Scalability**: Modular architecture with external runners
- **Flexibility**: Integration of heterogeneous components

---

## 🔄 Variants

- [**simplified-stack**](simplified-stack/README.en.md): Lightweight version optimized for local development that integrates Drupal, Obsidian, and Forgejo for isolated AI workflows.
- [**very-simplified-stack**](very-simplified-stack/README.en.md): Minimalist version that removes n8n orchestration and focuses on voice services and the Cognito agent API, designed to connect to an external Ollama instance.

---

## ✨ Main Features

- **Workflow automation** with n8n (port 5678)
  - Visual interface for creating complex workflows
  - External task runner system (JavaScript + Python)
  - Isolated execution of custom code

- **Local LLMs** with Ollama (port 11434)
  - Support for CPU and GPU (NVIDIA/AMD)
  - Pre-loaded models: Llama 3.2, Qwen, Deepseek-R1, etc.
  - No external API dependencies

- **Image generation** with ComfyUI (port 8188)
  - Stable Diffusion integrated
  - Optimized NVIDIA GPU support
  - Batch image processing

- **Collaboration and messaging** with Matrix Synapse (port 8008)
  - Federated chat server
  - Dedicated PostgreSQL database
  - Redis integration for sessions

- **Vector database** with Qdrant (port 6333)
  - Embedding storage
  - Semantic search for RAG
  - Data persistence

- **Secure remote access** with Zrok
  - Secure webhook tunneling
  - Public URLs for n8n
  - No ports exposed to the internet

---

## 🛡️ Security

The stack includes protection against brute force and DoS attacks using **Fail2ban**.

- **Protected Services:** n8n, Forgejo, Matrix Synapse.
- **Mechanism:** Monitors logs in real-time and blocks malicious IPs showing suspicious behavior (e.g., multiple failed login attempts).
- **Configuration:** Rules are located in the `fail2ban/` directory. By default, an IP is blocked for one hour after 5 failed attempts.

---

## 🤝 Contribution

We would love to receive contributions. Please:

1. **Fork** the repository
2. **Create a branch** for your feature (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open a Pull Request**

For more details, see [CONTRIBUTING.en.md](CONTRIBUTING.en.md)

---

## 📄 License

This project is licensed under the **GNU Affero General Public License v3 (AGPL-3.0)**

- ✅ You can use, modify and distribute
- ✅ You must include notice of changes
- ✅ If you use it over a network, you must share the source code
- 📖 [View full license](LICENSE.en.md)

---

## 📞 Contact & Resources

- **GitHub:** [Axlfc/connect-core](https://github.com/Axlfc/connect-core)
- **Issues:** [GitHub Issues](https://github.com/Axlfc/connect-core/issues)
- **Contribution Guide:** [CONTRIBUTING.en.md](CONTRIBUTING.en.md)
- **Technical Documentation:** [.github/copilot-instructions.en.md](.github/copilot-instructions.en.md)

---

<div align="center">

**Made with ❤️ by the cognito-stack team**

⭐ If you find it useful, give it a star!

</div>
