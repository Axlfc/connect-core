# RFC de Gobernanza Empresarial, Despliegue BYOC y Escalado Horizontal

- **Estado:** Propuesto (Documento de Arquitectura y Diseño)
- **Autor:** Equipo de Arquitectura de Cognito
- **Fecha:** 2026-08-26
- **Hallazgos Cubiertos:**
  - **AUD-007:** Ausencia de modelo de datos multi-tenant (`Organization`, `Project`, `User`, `Role`)
  - **AUD-008:** Inexistencia de autenticación federada SSO/SAML 2.0 / OIDC
  - **AUD-009:** Inexistencia de audit log estructurado exportable a SIEM / OTLP
  - **AUD-012:** Acoplamiento al sistema de archivos local (`./data/sessions/`) que bloquea despliegues BYOC / contenedores efímeros
  - **AUD-032:** Estado de sesión acoplado a SQLite y locks locales en memoria que bloquea el escalado horizontal multi-réplica

---

## 1. Resumen Ejecutivo y Metodología de Diseño

Este documento define la arquitectura de referencia para la gobernanza multi-tenant, la federación de identidades, la auditoría exportable a SIEM/OTLP y la capa de almacenamiento distribuido sin estado (stateless) para el arnés de agentes **Cognito**.

Se aborda explícitamente la unificación de los hallazgos **AUD-012** (acoplamiento a disco local para sesiones) y **AUD-032** (uso de SQLite + locks en memoria), reconociendo que representan dos manifestaciones del mismo problema de raíz: el almacenamiento de sesión acoplado al nodo local. La solución propuesta reemplaza el almacenamiento local por un diseño de **almacenamiento compartido híbrido (Relacional + Key-Value + Cache/Locks Distribuidos)**, habilitando la ejecución en contenedores efímeros BYOC (Bring Your Own Cloud) y el escalado horizontal activo-activo.

De acuerdo con la política de dependencias mínimas del proyecto:
1. **SSO / OIDC / SAML (AUD-008):** Se autoriza el uso de librerías maduras del ecosistema (`PyJWT`, `pysaml2` / `python-saml`, `cryptography`) para la verificación de firmas asimétricas y parsing de aserciones.
2. **Almacenamiento Compartido (AUD-012 / AUD-032):** Se autoriza el uso de clientes estándar del ecosistema (`asyncpg` / `psycopg3` para PostgreSQL y `redis-py` para Redis). No se reimplementan protocolos de red ni consensos distribuidos.
3. **Resto del sistema (Modelos, Auditoría, Mapeo):** Utiliza las capacidades nativas de Python y la librería estándar en conjunto con Pydantic/FastAPI existente en el repositorio.

---

## 2. Diseño del Modelo de Datos Multi-Tenant (AUD-007)

### 2.1. Entidades del Dominio

El modelo de datos introduce la jerarquía multi-inquilino estándar enterprise:

```
+-----------------------------------------------------------------------+
|                             Organization                              |
| (org_id, name, slug, sso_config, status, created_at)                  |
+-----------------------------------------------------------------------+
                                   | 1:N
             +---------------------+---------------------+
             |                                           |
             v 1:N                                       v 1:N
+-----------------------------------------+ +---------------------------+
|                 Project                 | |           User            |
| (project_id, org_id, name, slug, status)| | (user_id, org_id, email,  |
+-----------------------------------------+ |  sub, status, roles[])    |
                     | 1:N                  +---------------------------+
                     v                                   |
+--------------------------------------------------------+
|
v 1:N
+-----------------------------------------------------------------------+
|                                Session                                |
| (session_id, org_id, project_id, user_id, status, created_at, ...)    |
+-----------------------------------------------------------------------+
```

#### Esquema Relacional (DDL PostgreSQL)

```sql
-- Enums para estados y roles
CREATE TYPE org_status AS ENUM ('active', 'suspended', 'pending_deletion');
CREATE TYPE user_status AS ENUM ('active', 'inactive', 'deprovisioned');
CREATE TYPE rbac_role AS ENUM ('org_admin', 'project_admin', 'developer', 'auditor', 'anonymous_guest');
CREATE TYPE session_auth_type AS ENUM ('anonymous', 'authenticated_sso', 'api_key');

-- 1. Organización
CREATE TABLE organizations (
    org_id VARCHAR(64) PRIMARY KEY,
    slug VARCHAR(64) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    status org_status NOT NULL DEFAULT 'active',
    sso_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    sso_provider_config JSONB, -- Configuración OIDC/SAML por tenant
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Proyecto
CREATE TABLE projects (
    project_id VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
    slug VARCHAR(64) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_org_project_slug UNIQUE (org_id, slug)
);

-- 3. Usuario
CREATE TABLE users (
    user_id VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    external_subject_id VARCHAR(255), -- 'sub' de OIDC o NameID de SAML
    full_name VARCHAR(255),
    status user_status NOT NULL DEFAULT 'active',
    roles rbac_role[] NOT NULL DEFAULT '{developer}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMPTZ,
    CONSTRAINT uq_org_user_email UNIQUE (org_id, email),
    CONSTRAINT uq_org_external_sub UNIQUE (org_id, external_subject_id)
);

-- 4. Sesión (Evolución de la tabla de sesiones existente)
CREATE TABLE sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL REFERENCES organizations(org_id) ON DELETE RESTRICT,
    project_id VARCHAR(64) REFERENCES projects(project_id) ON DELETE SET NULL,
    user_id VARCHAR(64) REFERENCES users(user_id) ON DELETE SET NULL,
    auth_type session_auth_type NOT NULL DEFAULT 'anonymous',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_org_user ON sessions(org_id, user_id);
CREATE INDEX idx_sessions_updated_at ON sessions(updated_at);
```

### 2.2. Transición de Sesión Anónima a Sesión Vinculada (Claiming)

En entornos de desarrollo o evaluación inicial, una sesión puede comenzar en estado `anonymous` (sin `user_id` ni `org_id` explícitos, asignada a una organización por defecto `org-default-local`).

Cuando el usuario interactúa a través de la CLI o interfaz Web y ejecuta la autenticación SSO/OIDC:
1. El backend recibe el JWT/SAML verificado y obtiene el `user_id` y `org_id` correspondientes.
2. Se ejecuta un procedimiento atómico en PostgreSQL para actualizar el vínculo de la sesión:
   ```sql
   UPDATE sessions
   SET org_id = $1,
       user_id = $2,
       auth_type = 'authenticated_sso',
       updated_at = CURRENT_TIMESTAMP
   WHERE session_id = $3
     AND auth_type = 'anonymous';
   ```
3. Se actualizan las claves de la sesión en Redis (`session:{session_id}:meta`) asociando los campos `org_id` y `user_id` para reflejar la vinculación inmediatamente en todas las réplicas backend.

---

## 3. Propuesta de Almacenamiento Compartido (AUD-012 y AUD-032)

### 3.1. Evaluación de Opciones Tecnológicas

Para reemplazar la base de datos SQLite local, los locks en memoria de Python (`asyncio.Lock`) y los archivos en disco (`./data/sessions/`), se evaluaron tres alternativas de arquitectura:

| Criterio | Opción A: PostgreSQL + Redis (Elegida) | Opción B: AWS DynamoDB + ElastiCache Redis | Opción C: SQLite en NFS / EFS + File Locks |
|---|---|---|---|
| **Soporte BYOC / Cloud Agnostic** | **Excelente:** Desplegable en cualquier Kubernetes, AWS (RDS+ElastiCache), GCP, Azure o bare-metal. | **Bajo:** Dependencia exclusiva de AWS API (Vendor Lock-in). | **Medio:** Requiere montajes NFS/EFS con alta latencia de red. |
| **Escalado Horizontal y Concurrencia** | **Excelente:** PostgreSQL escala escrituras transaccionales; Redis gestiona sub/pub y locks distribuidos (Redlock). | **Excelente:** Altamente escalable pero requiere adaptación de consultas relacionales. | **Deficiente:** Locks de archivos NFS sufren de condiciones de carrera y latencias elevadas. |
| **Persistencia e Historial** | **Excelente:** Consultas relacionales complejas, auditoría e índices secundarios. | **Bueno:** Requiere índices secundarios globales (GSI) costosos. | **Bueno:** Pero propenso a corrupción ante desconexiones de red NFS. |
| **Compatibilidad con Ecosistema Python** | **Excelente:** Utiliza `asyncpg` y `redis-py` (estándares de la industria). | **Medio:** Utiliza `boto3` con llamadas síncronas/asíncronas custom. | **Excelente:** Módulos `sqlite3` y `fcntl` nativos. |

### 3.2. Justificación de la Opción Elegida (PostgreSQL + Redis)

Se selecciona la **Opción A (PostgreSQL + Redis)** por las siguientes razones:
1. **Solución unificada para AUD-012 y AUD-032:** Elimina cualquier dependencia de volúmenes persistentes locales (`./data/sessions/`). Los contenedores de `cognito-backend` pasan a ser 100% **stateless** (sin estado local), lo que permite matarlos, recrearlos o auto-escalarlos horizontalmente sin perder sesiones.
2. **Coordinación Distribuida Multi-Réplica (AUD-032):**
   - **Locks Distribuidos:** Reemplaza los `asyncio.Lock` en memoria local mediante cierres distribuidos basados en Redis (`Redlock` / `redis-py` locks con TTL automático).
   - **Streaming e Intercomunicación:** Permite la emisión de eventos SSE/WebSocket entre réplicas mediante canales **Redis Pub/Sub**.
3. **Persistencia Transaccional Cumplida:** PostgreSQL garantiza integridad ACID para organizaciones, usuarios, eventos de auditoría e historial de conversaciones.

### 3.3. Arquitectura de Almacenamiento Compartido

```
                   +----------------------------------+
                   |     Load Balancer / Ingress      |
                   +----------------------------------+
                                     |
             +-----------------------+-----------------------+
             |                                               |
             v                                               v
+------------------------+                       +------------------------+
|  cognito-backend (R1)  |                       |  cognito-backend (R2)  |
|  [Stateless Container] |                       |  [Stateless Container] |
+------------------------+                       +------------------------+
          |         |                                 |         |
          |         +-----------------------+         |         |
          |                                 |         |         |
          v                                 v         v         v
+----------------------------------+   +----------------------------------+
|           Redis Cluster          |   |       PostgreSQL Multi-AZ        |
| - Locks Distribuidos (Redlock)   |   | - Organizations, Users, Projects |
| - Caché de Sesión In-Memory      |   | - Persistence Historial Sesiones |
| - Redis Pub/Sub (Eventos SSE)    |   | - Audit Trail (SIEM Source)      |
+----------------------------------+   +----------------------------------+
```

---

## 4. Integración de Autenticación Federada SSO / OIDC / SAML (AUD-008)

### 4.1. Flujo de Autenticación OIDC / SAML 2.0

Para soportar la autenticación de operadores humanos desde la CLI o interfaces Web empresariales (e.g. Okta, Azure AD / Entra ID, Keycloak, PingIdentity):

```
User (CLI / Web)             Cognito Backend              IdP (Okta / Entra ID)
     |                             |                               |
     |--- 1. POST /api/auth/login ->|                               |
     |    (tenant_slug, provider)  |                               |
     |<-- 2. Return Auth URL ------|                               |
     |    (with state, PKCE code)  |                               |
     |                             |                               |
     |--- 3. Redirect to IdP Login ------------------------------->|
     |<-- 4. Redirect with Auth Code / SAMLResponse ---------------|
     |                             |                               |
     |--- 5. POST /api/auth/callback ----------------------------->|
     |    (code / SAMLResponse)    |                               |
     |                             |--- 6. Validate Signature ----|
     |                             |    (PyJWT / python-saml)      |
     |                             |--- 7. Map Claims to User -----|
     |                             |--- 8. Issue JWT Session Token |
     |<-- 9. Bearer Token + User --|                               |
```

### 4.2. Bibliotecas del Ecosistema Utilizadas
- **OIDC / JWT:** `PyJWT` (con `cryptography` como backend de verificación de firmas RSA/ECDSA RS256/ES256).
- **SAML 2.0:** `pysaml2` o `python3-saml` para la validación de firmas XML (XMLDSig) y desencriptación de aserciones.

### 4.3. Reglas de Mapeo de Claims de Identidad

El backend transformará las aserciones federadas en identidades del modelo Cognito:

```python
# Mapeo conceptual de claims OIDC/SAML a modelo de usuario
def map_federated_claims_to_user(claims: dict, org_id: str) -> UserDomainModel:
    external_sub = claims.get("sub") or claims.get("NameID")
    email = claims.get("email") or claims.get("urn:oidc:email")
    full_name = claims.get("name") or claims.get("displayName", "")

    # Mapeo de roles desde grupos del IdP (e.g., Okta Groups)
    idp_groups = claims.get("groups", []) or claims.get("roles", [])
    assigned_roles = []

    if "Cognito-Admins" in idp_groups:
        assigned_roles.append("org_admin")
    if "Cognito-Auditors" in idp_groups:
        assigned_roles.append("auditor")
    if not assigned_roles:
        assigned_roles.append("developer") # Default RBAC role

    return UserDomainModel(
        org_id=org_id,
        email=email,
        external_subject_id=external_sub,
        full_name=full_name,
        roles=assigned_roles,
    )
```

---

## 5. Esquema de Audit Log Estructurado y Exportación SIEM/OTLP (AUD-009)

### 5.1. Campos del Registro de Auditoría

Cada evento de auditoría captura de forma inmutable el contexto completo de la acción realizada por el agente o el operador humano.

| Campo | Tipo | Descripción |
|---|---|---|
| `audit_id` | `UUIDv4` | Identificador único global del registro de auditoría. |
| `timestamp` | `ISO-8601 UTC` | Fecha y hora de alta precisión (`YYYY-MM-DDTHH:mm:ss.ffffffZ`). |
| `org_id` | `String` | Organización a la que pertenece la ejecución. |
| `project_id` | `String` | Proyecto asociado a la sesión (si aplica). |
| `session_id` | `String` | Identificador de la sesión activa del agente. |
| `user_id` | `String` | Identificador del usuario humano autenticado. |
| `actor` | `JSON Object` | Detalle del actor: `{ "type": "user"|"agent"|"system", "id": "...", "email": "..." }`. |
| `action` | `String` | Operación ejecutada (e.g. `tool.bash.execute`, `file.edit`, `approval.decision`). |
| `resource` | `String` | Recurso objetivo (e.g. `/workspace/app/main.py`, `bash_command`). |
| `trace_id` | `String` | **Identificador de trazabilidad propagado de AUD-025** (`trace_id` de W3C Context). |
| `request_id` | `String` | Identificador de la petición HTTP/WebSocket originaria. |
| `status` | `String` | Resultado de la acción: `SUCCESS`, `DENIED`, `FAILED`, `TIMED_OUT`. |
| `approval_metadata` | `JSON Object` | **Reutilización de AUD-021:** Captura la estructura `ApprovalDecisionAudit` si la acción requirió aprobación humana. |
| `security_context` | `JSON Object` | Banderas de riesgo (`is_destructive`, `is_read_only`), sandbox status, red saliente. |

### 5.2. Ejemplo de Evento JSON Estructurado

```json
{
  "audit_id": "aud-8f92a11b-4c3e-4f12-8a90-123456789abc",
  "timestamp": "2026-08-26T14:32:00.102938Z",
  "org_id": "org-acme-corp",
  "project_id": "proj-backend-core",
  "session_id": "sess-991203812",
  "user_id": "usr-usr_01H9A",
  "actor": {
    "type": "agent",
    "id": "cognito-agent-v1",
    "delegated_by_user": "usr-usr_01H9A",
    "user_email": "dev-lead@acme.com"
  },
  "action": "tool.bash.execute",
  "resource": "git reset --hard HEAD~1",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "request_id": "req-c1209381023",
  "status": "APPROVED",
  "approval_metadata": {
    "approval_id": "appr-3a1029102",
    "session_id": "sess-991203812",
    "action": "git reset --hard HEAD~1",
    "actor": "dev-lead@acme.com",
    "timestamp": "2026-08-26T14:31:58.901234Z",
    "status": "approved",
    "reason": "Aprobado manualmente desde panel de control"
  },
  "security_context": {
    "is_destructive": true,
    "is_read_only": false,
    "sandbox_active": true,
    "network_isolated": true
  }
}
```

### 5.3. Reutilización del Registro de Decisiones de AUD-021

El módulo `ApprovalManager` en `app/core/approval.py` ya genera estructuras `ApprovalDecisionAudit`. El motor de auditoría interceptará cada decisión emitida por `ApprovalManager` y la envolverá automáticamente en un evento del Audit Log, publicándolo hacia las salidas configuradas (PostgreSQL + Syslog / OTLP).

### 5.4. Formatos de Exportación e Integración SIEM/OTLP

El backend soportará dos exportadores configurables vía variable de entorno (`COGNITO_AUDIT_EXPORTER`):
1. **SIEM Exporter (Syslog CEF / JSON Stream):** Envía eventos vía UDP/TCP/TLS Syslog estructurado en formato CEF (Common Event Format) o JSON a colectores como Splunk, Datadog o Elastic.
2. **OTLP Logs Exporter:** Exporta logs estructurados utilizando el protocolo OpenTelemetry (OTLP/gRPC u OTLP/HTTP) hacia un OTel Collector corporativo.

---

## 6. Plan de Migración de Datos de Sesión Existentes

Para migrar los entornos de ejecución actuales que almacenan sesiones en SQLite local y archivos en `./data/sessions/` sin pérdida de historial ni tiempos de inactividad no planificados:

### Fase 1: Extracción y Lectura Dual (Dual-Read)
1. **Script de Migración de Esquemática (`migrate_sqlite_to_postgres.py`):**
   - Parsea los archivos `.db` SQLite locales ubicados en `./data/sessions/` y la tabla SQLite `sessions`.
   - Convierte los registros de sesiones, mensajes e historial de ejecuciones en inscripciones equivalentes en PostgreSQL.
   - Asigna las sesiones legacy existentes a una organización por defecto denominada `org-legacy-migrated` y al usuario `usr-legacy-admin`.

### Fase 2: Escritura Dual (Dual-Write)
1. Durante el despliegue del nuevo backend con almacenamiento compartido, el servicio escribirá los estados de sesión nuevos tanto en Redis/PostgreSQL como (opcionalmente) en el almacenamiento local como fallback temporal.
2. Una tarea en segundo plano verifica que los conteos de mensajes e checksums de historial en PostgreSQL coincidan con el SQLite migrado.

### Fase 3: Conmutación Definitiva (Cutover)
1. Se desactiva la lectura/escritura en SQLite local mediante configuración (`COGNITO_STORAGE_BACKEND=postgres_redis`).
2. El directorio `./data/sessions/` se archiva como respaldo comprimido de seguridad y se libera de la ruta de ejecución principal.

---

## 7. Hoja de Ruta por Fases y Estimación de Esfuerzo

Dado que las capacidades de **control presupuestario multi-tenant (AUD-010)**, **retención/borrado GDPR (AUD-011)** y **checkpointing por turno (AUD-026)** dependen fundamentalmente del modelo de datos y del almacenamiento compartido, la hoja de ruta prioriza esta base funcional:

| Fase | Descripción del Alcance | Hallazgos Atendidos / Desbloqueados | Tamaño Relativo |
|---|---|---|---|
| **Fase 1** | **Base de Datos Multi-Tenant & Storage Compartido (PostgreSQL + Redis):**<br>- Creación de esquemas DDL `Organization`, `Project`, `User`, `Session`.<br>- Implementación de `PostgresSessionManager` y `RedisLockManager`.<br>- Refactorización de contenedores backend a stateless. | Atiende **AUD-007**, **AUD-012**, **AUD-032**.<br>*Desbloquea:* AUD-010, AUD-011, AUD-026. | **XL** (Extra Large) |
| **Fase 2** | **Autenticación Federada SSO / OIDC / SAML 2.0:**<br>- Integración de `PyJWT` y `python-saml`.<br>- Endpoints `/api/auth/login` y `/api/auth/callback`.<br>- Mapeo de claims a usuarios y RBAC. | Atiende **AUD-008**. | **L** (Large) |
| **Fase 3** | **Audit Log Estructurado, SIEM & OTLP:**<br>- Motor de auditoría unificado con `trace_id` de AUD-025.<br>- Integración de `ApprovalDecisionAudit` de AUD-021.<br>- Exportadores Syslog CEF y OTLP. | Atiende **AUD-009**. | **M** (Medium) |
| **Fase 4** | **Migración de Datos y Gobernanza Derivada:**<br>- Ejecución del plan de migración de sesiones legacy.<br>- Implementación de presupuesto de tokens por Org (AUD-010), políticas de retención (AUD-011) y checkpointing transaccional (AUD-026). | Atiende **AUD-010**, **AUD-011**, **AUD-026**. | **L** (Large) |

---

## 8. Alternativas Descartadas y Justificación

### 8.1. Alternativa Descartada para Almacenamiento: SQLite sobre NFS / AWS EFS

- **Descripción:** Mantener la arquitectura basada en archivos SQLite pero guardando la base de datos y los archivos de sesión en un sistema de archivos de red compartido (NFS v4 o AWS EFS) montado en cada réplica del backend.
- **Motivo del Descarte:**
  1. **Corrupción por Locks de Red:** SQLite utiliza cierres de archivos de POSIX (`fcntl`). En sistemas de archivos distribuidos como NFS/EFS, el bloqueo de archivos a través de la red no es completamente confiable y causa latencias excesivas, bloqueos mutuos (deadlocks) o corrupción de la base de datos ante picos de concurrencia.
  2. **Incompatibilidad con Escalado Horizontal (AUD-032):** No resuelve la necesidad de coordinación en tiempo real entre réplicas (Pub/Sub para eventos SSE o comunicación inter-proceso).

### 8.2. Alternativa Descartada para Modelo de Datos: Modelo Inquilino Silo (Database-per-Tenant)

- **Descripción:** Crear una base de datos PostgreSQL física totalmente independiente por cada Organización (`cognito_db_org_1`, `cognito_db_org_2`).
- **Motivo del Descarte:**
  1. **Sobrecarga Operativa Excesiva:** Gestionar cientos o miles de bases de datos individuales complica drásticamente las migraciones de esquemas (Alembic) y el mantenimiento de conexiones en el pool.
  2. **Inadecuado para SaaS / BYOC Flexible:** El modelo **Inquilino Discriminado por Columna (`org_id`)** con Row Level Security (RLS) en PostgreSQL ofrece un aislamiento lógico garantizado y auditado con una complejidad de infraestructura significativamente menor.

---

## 9. Conclusión y Próximos Pasos

Este RFC establece las bases para transformar Cognito en una plataforma de agentes enterprise 2026. Al unificar la estrategia de almacenamiento compartido en PostgreSQL y Redis, se resuelven simultáneamente las barreras de despliegues BYOC efímeros (AUD-012) y el escalado horizontal (AUD-032), despejando el camino para la gobernanza multi-tenant completa, SSO y auditoría SIEM.

Tras la aprobación de este plan de diseño por parte de los revisores, se procederá a iniciar la implementación de la **Fase 1** según el desglose detallado en la hoja de ruta.
