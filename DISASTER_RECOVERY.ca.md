# Guía de Recuperación ante Desastres (Disaster Recovery)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.zh-cn.md)


## 1. Introducción

Este documento describe la estrategia de copias de seguridad y los procedimientos de restauración para el stack `Cognito-Stack`. El objetivo es asegurar la integridad y disponibilidad de los datos críticos en caso de un fallo del sistema, corrupción de datos o cualquier otro evento catastrófico.

La estrategia se basa en el uso de **Duplicati**, un cliente de copias de seguridad de código abierto que se ejecuta como un contenedor dentro del stack.

## 2. Acceso a Duplicati

La interfaz web de Duplicati está disponible en el siguiente `URL`:

- **URL:** `http://duplicati.localhost` (o el dominio que hayas configurado)
- **Acceso:** Protegido por Authelia. Deberás iniciar sesión con tus credenciales.

## 3. Configuración de un Trabajo de Copia de Seguridad

A continuación, se detalla el procedimiento para crear un trabajo de copia de seguridad para los datos más críticos del sistema.

### Paso 1: Añadir una nueva copia de seguridad

1.  En la interfaz de Duplicati, haz clic en **"Add backup"**.
2.  Selecciona **"Configure a new backup"** y haz clic en "Next".

### Paso 2: Configuración general

1.  **Name:** Asigna un nombre descriptivo (ej. "Cognito-Stack Critical Data").
2.  **Encryption:** Se recomienda encarecidamente **habilitar el cifrado**. Selecciona "AES-256 encryption, built-in" y genera una contraseña segura. **¡Guarda esta contraseña en un lugar seguro! Sin ella, no podrás restaurar tus datos.**
3.  Haz clic en "Next".

### Paso 3: Destino de la copia de seguridad

1.  **Storage Type:** Elige dónde quieres almacenar tus copias de seguridad. Duplicati soporta una gran variedad de destinos, como `SFTP`, `WebDAV`, `Google Drive`, `Amazon S3`, etc.
2.  **Local folder or drive:** Para este ejemplo, usaremos un directorio local en el `host`. La ruta dentro del contenedor que apunta a un directorio en el `host` es `/backups`.
    - **Path:** `/backups`
3.  Configura las credenciales o la información de conexión necesaria para tu destino elegido.
4.  Haz clic en **"Test connection"** para verificar que Duplicati puede acceder al destino.
5.  Haz clic en "Next".

### Paso 4: Datos de origen

1.  Esta es la parte más importante. Aquí seleccionarás los directorios que quieres respaldar. Los datos de los servicios de Docker se encuentran en el directorio `/source` dentro del contenedor de Duplicati.
2.  Expande el árbol de directorios y selecciona los siguientes volúmenes, que contienen los datos más críticos:
    - `postgres_storage`
    - `n8n_storage`
    - `forgejo_data`
    - `redis_data`
    - `qdrant_storage`
    - `matrix_data`
    - `authelia` (para la configuración de usuarios)
3.  Haz clic en "Next".

### Paso 5: Programación

1.  Define con qué frecuencia quieres que se ejecuten las copias de seguridad. Se recomienda una copia de seguridad **diaria**.
2.  Selecciona una hora en la que el sistema tenga poca carga (ej. 3:00 AM).
3.  Haz clic en "Next".

### Paso 6: Opciones de la copia de seguridad

1.  **Remote volume size:** Ajusta el tamaño de los volúmenes de la copia de seguridad. Un valor de `50 MB` es un buen punto de partida.
2.  **Backup retention:** Define cuánto tiempo quieres conservar las copias de seguridad. Se recomienda **"Keep a specific number of backups"** y establecer un valor como `14` para tener dos semanas de historial.
3.  Haz clic en **"Save"**.

## 4. Procedimiento de Restauración

En caso de que necesites restaurar los datos, sigue estos pasos:

### Paso 1: Detener los servicios

Antes de restaurar, es crucial detener todos los servicios para evitar inconsistencias en los datos.

```bash
./stop.sh
```

### Paso 2: Acceder a la restauración en Duplicati

1.  Abre la interfaz de Duplicati.
2.  Haz clic en el trabajo de copia de seguridad que quieres restaurar.
3.  Haz clic en **"Restore"**.

### Paso 3: Seleccionar los archivos a restaurar

1.  Selecciona la fecha de la copia de seguridad que quieres restaurar.
2.  Puedes restaurar todos los archivos o seleccionar directorios específicos. Para una recuperación completa, selecciona todos los directorios.
3.  Haz clic en "Continue".

### Paso 4: Opciones de restauración

1.  **Restore to original location:** Selecciona esta opción para restaurar los archivos a sus directorios originales.
2.  **Overwrite:** Selecciona "Overwrite" para reemplazar cualquier archivo existente (corrupto) con la versión de la copia de seguridad.
3.  Haz clic en **"Restore"**.

### Paso 5: Verificar y reiniciar los servicios

1.  Una vez que la restauración se haya completado, verifica que los archivos se han restaurado correctamente en los volúmenes de Docker en el `host`.
2.  Reinicia el stack de `Cognito-Stack`.

```bash
./start.sh
```

## 5. Conclusión

Esta guía proporciona los pasos fundamentales para asegurar y restaurar los datos de `Cognito-Stack`. Es responsabilidad del administrador del sistema asegurarse de que las copias de seguridad se configuren correctamente, se ejecuten de forma regular y se prueben periódicamente.
