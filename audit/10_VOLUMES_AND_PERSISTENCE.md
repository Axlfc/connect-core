# AUDIT 10: GESTIÓN DE VOLÚMENES Y PERSISTENCIA
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.zh-cn.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✓ | **Estrategia de Persistencia** | La estrategia de utilizar volúmenes nombrados de Docker para todos los datos de estado (`postgres_storage`, `n8n_storage`, etc.) es **correcta y robusta**. Separa el ciclo de vida de los datos del de los contenedores. |
| ✓ | **Intención de Backup** | La presencia de un servicio `duplicati` y un `duplicati-job-template.json` demuestra una **clara intención de implementar backups**, lo cual es fundamental para la resiliencia de los datos. |
| ⚠️ | **Permisos de Volúmenes** | El script `inspect_volumes.sh` requiere `sudo` para calcular el tamaño de los volúmenes (`du -sh`). Esto sugiere que los permisos de los directorios de volúmenes en el host pueden no estar correctamente alineados con los usuarios del sistema, lo que podría llevar a problemas de permisos en tiempo de ejecución. |
| ✗ | **Estrategia de Backup No Implementada** | El sistema **carece de una estrategia de backup automatizada y funcional**. El `duplicati-job-template.json` es solo una plantilla; no hay ningún script o mecanismo que configure automáticamente el trabajo de backup en Duplicati, dejando el proceso enteramente manual y propenso a errores. |
| ✗ | **Sin Procedimientos de Recuperación (Recovery)** | No existe un procedimiento de recuperación de desastres documentado o probado. Las únicas referencias a la restauración son comandos de `docker` en la salida de `inspect_volumes.sh`, lo cual es **insuficiente para un entorno de producción**. |

---

## 2. Hallazgos Detallados

### ✓ Lo que está bien

1.  **Uso de Volúmenes Nombrados:**
    *   El `docker-compose.yml` define explícitamente volúmenes nombrados para cada servicio con estado. Esto es una mejor práctica en comparación con los montajes de `bind` para datos, ya que los volúmenes son gestionados por el motor de Docker y son más portables y fáciles de manejar.

2.  **Plantilla de Backup Bien Definida:**
    *   El archivo `backups/duplicati-job-template.json` define un trabajo de backup sólido:
        *   **Fuentes Claras:** Identifica correctamente los directorios clave a respaldar (`./shared`, `./data`, `./models`).
        *   **Cifrado Habilitado:** Especifica `encryption-module: aes`, lo cual es crucial para la seguridad de los backups.
        *   **Programación Diaria:** El `Schedule: "@daily"` es un punto de partida razonable para la mayoría de los casos de uso.

### ✗ Problemas Encontrados

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **V-01** | **ALTO** | **Proceso de Backup Manual** | No hay automatización para configurar Duplicati. Un administrador debe: 1) Iniciar el stack. 2) Acceder a la UI de Duplicati. 3) Crear un nuevo trabajo de backup. 4) Configurar el destino. 5) Configurar la passphrase de cifrado. 6) Seleccionar los directorios fuente. Este proceso manual es propenso a errores de configuración y puede ser fácilmente olvidado. |
| **V-02** | **ALTO** | **Ausencia de Plan de Recuperación de Desastres** | Si el servidor host falla catastróficamente, no hay una guía paso a paso que describa cómo restaurar los servicios y los datos en un nuevo host. Esto aumenta significativamente el Tiempo de Recuperación (RTO) y el riesgo de pérdida de datos si la restauración se realiza incorrectamente. |
| **V-03** | **MEDIO** | **Potenciales Problemas de Permisos en Volúmenes** | El hecho de que se necesite `sudo` para inspeccionar el tamaño de los volúmenes en el script de diagnóstico es un "code smell". Indica que los UID/GID de los procesos dentro de los contenedores podrían no coincidir con la propiedad de los archivos en el host, una causa común de errores de "permiso denegado" en producción. |

### ⚠️ Warnings/Recomendaciones

1.  **Backup de Bases de Datos:**
    *   El backup actual se basa en copiar los archivos del volumen de la base de datos (`postgres_storage`). Esto se conoce como un backup "en frío" o de sistema de archivos. Para garantizar la consistencia de los datos, la mejor práctica es utilizar herramientas específicas de la base de datos como `pg_dump`. El backup actual podría capturar la base de datos en un estado inconsistente si se está escribiendo en ella durante el proceso.

2.  **Pruebas de Restauración:**
    *   Un plan de backup no está completo hasta que el proceso de restauración ha sido probado. No hay evidencia de que se hayan realizado pruebas de restauración.

### 🔧 Soluciones Sugeridas

1.  **Para V-01 (Automatizar la Configuración de Duplicati):**
    *   **Solución:** Crear un script de inicialización para Duplicati.
        1.  **Crear un Script (`scripts/init_duplicati.sh`):** Este script utilizaría la API de Duplicati o su CLI (`duplicati-cli`) para configurar el trabajo de backup automáticamente en el primer inicio.
        2.  **Lógica del Script:**
            *   Esperar a que la API de Duplicati esté disponible.
            *   Leer variables de entorno (ej. `DUPLICATI_DESTINATION`, `DUPLICATI_PASSPHRASE`) del archivo `.env`.
            *   Usar `sed` o una herramienta similar para reemplazar los placeholders en `duplicati-job-template.json`.
            *   Hacer un `POST` del JSON resultante al endpoint de la API de Duplicati para crear/actualizar el trabajo.
        3.  **Ejecutar el Script:** Ejecutar este script como un servicio de `docker-compose` que se ejecuta una vez al inicio, o como parte del script `start.sh`.

2.  **Para V-02 (Crear un Plan de Recuperación):**
    *   **Solución:** Crear un documento `DISASTER_RECOVERY.md`.
        *   **Contenido del Documento:**
            *   **Requisitos Previos:** (ej. nuevo host con Docker instalado).
            *   **Paso 1: Restaurar Backups:** Instrucciones detalladas sobre cómo usar la UI o CLI de Duplicati para restaurar los datos desde el almacenamiento de destino a un directorio temporal.
            *   **Paso 2: Re-inicializar el Stack:** Cómo clonar el repositorio, ejecutar `init_env.sh` y `setup-permissions.sh`.
            *   **Paso 3: Importar Datos Restaurados:** Comandos `docker cp` o de montaje de volúmenes para mover los datos restaurados a los nuevos volúmenes de Docker.
            *   **Paso 4: Verificación:** Cómo verificar que los servicios se han iniciado correctamente y que los datos están intactos.
        *   **Pruebas:** Este procedimiento debe ser probado al menos una vez para garantizar que funciona como se espera.

3.  **Para V-03 (Solucionar Permisos):**
    *   **Solución:** Expandir y hacer cumplir el uso de `setup-permissions.sh`.
        *   Asegurarse de que el script `setup-permissions.sh` crea los directorios en el host para **todos** los volúmenes que lo necesiten, no solo para los logs.
        *   Utilizar las variables `PUID` y `PGID` del archivo `.env` de forma consistente en todos los servicios de `docker-compose.yml` y en el script `setup-permissions.sh` para que los permisos coincidan.
