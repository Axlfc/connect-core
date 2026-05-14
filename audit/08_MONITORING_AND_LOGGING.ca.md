# AUDIT 08: MONITORATGE, LOGGING I OBSERVABILITAT
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Recollida de Mètriques** | L'stack de Prometheus està **ben configurat** per recollir mètriques clau de la infraestructura, incloent mètriques del host (`node-exporter`), dels contenidors (`cadvisor`), i mètriques especialitzades de GPU (`nvidia-dcgm-exporter`). |
| ✓ | **Provisioning de Grafana** | L'enfocament de GitOps per a la configuració de Grafana és **excel·lent**. Tant la font de dades de Prometheus com els dashboards es provisionen automàticament, cosa que assegura consistència i reproductibilitat. |
| ⚠️ | **Visibilitat Limitada** | Els dashboards existents se centren gairebé exclusivament en mètriques dels serveis d'IA (Ollama, GPU). **Manquen dashboards crucials** per a la salut general del sistema i dels contenidors, cosa que crea punts cecs importants. |
| ✗ | **Sense Sistema d'Alertes** | La configuració de Prometheus **manca completament d'una secció d' `alerting` i de `rule_files`**. Això significa que el sistema no pot notificar proactivament els operadors sobre fallades de servei, esgotament de recursos o comportament anòmal. El monitoratge és purament passiu. |
| ✗ | **Logging No Centralitzat** | No existeix un sistema d'agregació de logs (com l'stack ELK/Loki). Els logs s'escriuen en fitxers dins de volums de Docker o en la sortida estàndard (`stdout`). Això fa que la correlació d'esdeveniments entre diferents serveis sigui **extremadament difícil i lenta**, especialment durant la investigació d'un incident. |
| ✗ | **Accés Insegur a Logs** | No hi ha un mecanisme centralitzat i securitzat per accedir als logs. Per a revisar els logs, un operador necessitaria accés directe al sistema de fitxers del host de Docker, la qual cosa és una mala pràctica de seguretat que viola el principi de mínim privilegi. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Base de Mètriques Sòlida:**
    *   La configuració de `prometheus.yml` és robusta. Inclou `scrape_configs` per a `node-exporter` (mètriques del host), `cadvisor` (mètriques de contenidors), `nvidia-dcgm-exporter` (mètriques de GPU), i el `blackbox-exporter` per a health checks d'endpoints d'aplicació. Aquesta és una base excel·lent per a l'observabilitat.

2.  **Infraestructura com a Codi (IaC) per a Monitoratge:**
    *   Grafana es provisiona a través de fitxers YAML (`grafana/provisioning`), la qual cosa significa que la configuració de la font de dades i els dashboards està versionada a Git. Aquesta és una pràctica moderna i molt recomanada que evita la configuració manual i la deriva de configuració.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **M-01** | **CRÍTIC** | **Absència Total d'Alertes** | Si un servei crític com `postgres` o `authelia` cau, o si el disc del servidor s'omple, **ningú serà notificat**. La fallada només es descobrirà quan els usuaris reportin problemes, la qual cosa augmenta dràsticament el Temps Mig de Detecció (MTTD) i el Temps Mig de Resolució (MTTR). |
| **M-02** | **ALT** | **Falta d'Agregació de Logs** | Durant un incident de seguretat o una fallada en cascada, és crucial poder veure una seqüència d'esdeveniments correlacionada en el temps a través de múltiples serveis. Sense un sistema de logging centralitzat, aquesta tasca és manual, lenta i propensa a errors, cosa que dificulta enormement l'anàlisi de la causa arrel. |
| **M-03** | **MITJÀ** | **Punts Cecs als Dashboards** | Tot i que existeixen dashboards per a Ollama, no n'hi ha cap per a visualitzar mètriques vitals del host (CPU, memòria, I/O de disc, ús de xarxa del `node-exporter`) ni per a la salut general dels contenidors (ús de recursos, reinicis, estat del `cadvisor`). Això impedeix la detecció proactiva de problemes de rendiment o de capacitat. |

---

### ⚠️ Avisos/Recomanacions

1.  **Retenció de Mètriques:**
    *   Prometheus està configurat amb una retenció de 15 dies (`--storage.tsdb.retention.time=15d`). Això és baix per a anàlisis de tendències a llarg termini. S'hauria de considerar l'ús d'una solució d'emmagatzematge a llarg termini com Thanos o VictoriaMetrics si es necessita un historial més extens.

2.  **Seguretat de Grafana:**
    *   Les credencials d'administrador de Grafana s'estableixen a través de variables d'entorn, la qual cosa és millor que tenir-les hardcodejades. Tanmateix, la contrasenya per defecte és `admin`. El `docker-compose.yml` ha d'incloure un comentari clar que indiqui que aquesta contrasenya s'ha de canviar immediatament després del primer inici de sessió.

---

### 🔧 Solucions Suggerides

1.  **Per a M-01 (Implementar Alertes):**
    *   **Solució:** Integrar `Alertmanager` a l'stack de monitoratge.
        1.  **Afegir `Alertmanager` a `docker-compose.yml`:**
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
        2.  **Crear `prometheus/alertmanager.yml`:** Configurar els receptors de notificacions (ex. Email, Slack, Telegram).
        3.  **Actualitzar `prometheus.yml`:** Afegir la configuració perquè Prometheus enviï les alertes a Alertmanager i carregar els fitxers de regles.
            ```yaml
            # A prometheus.yml
            alerting:
              alertmanagers:
                - static_configs:
                    - targets: ['alertmanager:9093']

            rule_files:
              - "/etc/prometheus/alert-rules.yml"
            ```
        4.  **Crear `prometheus/alert-rules.yml`:** Definir regles d'alerta crítiques (ex. `HostHighCpuLoad`, `ContainerDown`, `DiskSpaceLow`).

2.  **Per a M-02 (Centralitzar Logs):**
    *   **Solució:** Afegir `Loki` i `Promtail` a l'stack per a l'agregació de logs.
        1.  **Afegir `Loki` i `Promtail` a `docker-compose.yml`:**
            ```yaml
            loki:
              image: grafana/loki:2.9.0
              # ... configuració de Loki ...
            promtail:
              image: grafana/promtail:2.9.0
              # ... configuració de Promtail per recollir logs de contenidors ...
            ```
        2.  **Configurar Grafana:** Afegir Loki com una nova font de dades per a poder explorar i visualitzar els logs juntament amb les mètriques.

3.  **Per a M-03 (Millorar la Visibilitat):**
    *   **Solució:** Afegir dashboards estàndard de la comunitat per a `node-exporter` i `cadvisor`.
        *   Descarregar els JSON de dashboards populars des del [Marketplace de Grafana](https://grafana.com/grafana/dashboards/), com el "Node Exporter Full" (ID 1860) i el de "Docker and System Monitoring" (ID 893).
        *   Afegir-los al directori `grafana/dashboards/` perquè siguin provisionats automàticament.
