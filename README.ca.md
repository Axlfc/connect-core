# cognito-stack 🚀
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/README.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/README.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/README.zh-cn.md)


[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-3.8+-2496ED?logo=docker)](https://docs.docker.com/compose/)
[![n8n](https://img.shields.io/badge/n8n-1.121.0-red)](https://n8n.io/)
[![Status](https://img.shields.io/badge/Status-Actiu-brightgreen)](https://github.com/Axlfc/connect-core)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?logo=node.js)](https://nodejs.org/)

**connect-core**, o **cognito-stack** és una plataforma modular d'orquestració d'IA containeritzada que integra automatització de workflows, generació d'imatges i intel·ligència artificial local en un únic stack Docker Compose reproduïble i escalable. Suporta múltiples runtimes de contenidors (Docker i Podman) i perfils de maquinari (CPU, NVIDIA GPU, AMD GPU).

> ⚠️ **Advertència de Seguretat:** Aquest projecte es troba en desenvolupament actiu i no s'ha de desplegar en un entorn de producció sense una auditoria de seguretat exhaustiva.

## 📋 Taula de continguts

- [Descripció](#descripció)
- [Variants](#-variants)
- [Característiques principals](#-característiques-principals)
- [Problema que resol](#-problema-que-resol)
- [Casos d'ús](#-casos-dús)
- [Estructura del projecte](#-estructura-del-proyecto)
- [Requisits previs](#-requisits-previs)
- [Instal·lació de Docker](#-instal·lació-de-docker)
- [Runtimes de contenidors](#-runtimes-de-contenidors) ⭐ **Nou: Suport Podman**
- [Matriu de Compatibilitat Multi-Arquitectura](#-matriu-de-compatibilitat-multi-arquitectura) ⭐ **Nou: Apple Silicon**
- [Instal·lació del projecte](#-instal·lació-del-projecte)
- [Configuració](#-configuració)
- [Ús](#-ús)
- [Serveis de veu](#-voice-services)
- [Arquitectura](#-arquitectura)
- [Tecnologies utilitzades](#-tecnologies-utilitzades)
- [API i punts d'integració](#-api-i-punts-dintegració)
- [CI/CD Pipeline](#-cicd-pipeline)
- [Solució de problemes](#-solució-de-problemes)
- [Contribució](#-contribució)
- [Llicència](#-llicència)
- [Contacte](#-contacte)

---

## Descripció

**cognito-stack** és una solució empresarial per orquestrar pipelines d'intel·ligència artificial i automatització sense dependre d'APIs externes pagades ni perdre el control de les dades. Combina eines de codi obert líders en la indústria en una arquitectura containeritzada altament personalitzable que es pot executar en qualsevol màquina amb Docker.

La plataforma està dissenyada per a desenvolupadors, científics de dades i equips d'IA que necessiten:
- **Reproduïabilitat**: Entorn idèntic en qualsevol màquina
- **Privadesa**: Els models i les dades romanen locals
- **Escalabilitat**: Arquitectura modular amb runners externs
- **Flexibilitat**: Integració de components heterogenis

---

## 🔄 Variants

- [**simplified-stack**](simplified-stack/README.ca.md): Versió lleugera optimitzada per al desenvolupament local que integra Drupal, Obsidian i Forgejo per a fluxos de treball d'IA aïllats.
- [**very-simplified-stack**](very-simplified-stack/README.ca.md): Versió minimalista que elimina l'orquestració de n8n i es centra en serveis de veu i l'API d'agent Cognito, dissenyada per connectar amb una instància d'Ollama externa.

---

## ✨ Característiques principals

- **Automatització de workflows** amb n8n (port 5678)
  - Interfície visual per crear workflows complexos
  - Sistema de task runners externs (JavaScript + Python)
  - Execució aïllada de codi personalitzat

- **LLMs locals** amb Ollama (port 11434)
  - Suport per a CPU i GPU (NVIDIA/AMD)
  - Models precarregats: Llama 3.2, Qwen, Deepseek-R1, etc.
  - Sense dependències d'APIs externes

- **Generació d'imatges** amb ComfyUI (port 8188)
  - Stable Diffusion integrat
  - Suport GPU NVIDIA optimitzat
  - Processament en lot d'imatges

- **Col·laboració i missatgeria** amb Matrix Synapse (port 8008)
  - Servidor de xat federat
  - Base de dades PostgreSQL dedicada
  - Integració amb Redis per a sessions

- **Base de dades vectorial** amb Qdrant (port 6333)
  - Emmagatzematge d'embeddings
  - Cerca semàntica per a RAG
  - Persistència de dades

- **Accès segur remot** amb Zrok
  - Tunelització segura de webhooks
  - URLs públiques per a n8n
  - Sense exposar ports a internet

---

## 🛡️ Seguretat

L'stack inclou protecció contra atacs de força bruta i DoS mitjançant **Fail2ban**.

- **Serveis Protegits:** n8n, Forgejo, Matrix Synapse.
- **Mecanisme:** Monitoritza logs en temps real i bloqueja IPs malicioses que mostren comportament sospitós (ex. múltiples intents de login fallits).
- **Configuració:** Les regles es troben al directori `fail2ban/`. Per defecte, una IP és bloquejada per una hora després de 5 intents fallits.

---

## 🤝 Contribució

Ens encantaria rebre contribucions. Per favor:

1. **Fes un fork** del repositori
2. **Crea una branca** per a la teva funcionalitat (`git checkout -b feature/AmazingFeature`)
3. **Fes commit** dels teus canvis (`git commit -m 'Add AmazingFeature'`)
4. **Puja** la branca (`git push origin feature/AmazingFeature`)
5. **Obre un Pull Request**

Per a més detalls, vegeu [CONTRIBUTING.ca.md](CONTRIBUTING.ca.md)

---

## 📄 Llicència

Aquest projecte està llicenciat sota la **GNU Affero General Public License v3 (AGPL-3.0)**

- ✅ Pots utilitzar, modificar i distribuir
- ✅ Has d'incloure avís de canvis
- ✅ Si l'utilitzes en xarxa, has de compartir el codi font
- 📖 [Veure llicència completa](LICENSE.ca.md)

---

<div align="center">

**Fet amb ❤️ per l'equip de cognito-stack**

⭐ Si et resulta útil, dona una estrella!

</div>
