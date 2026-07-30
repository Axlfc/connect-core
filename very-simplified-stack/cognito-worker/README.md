# 🛠️ Cognito Worker — Workspace & Git Worktree Execution Service
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](README.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](README.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](README.zh-cn.md)

Este servicio (`cognito-worker`) es el componente de ejecución del lado del host que se comunica con el plano de control (`cognito-backend`). Proporciona una API interna aislada y segura para la creación de entornos de trabajo (git worktrees), verificación de cambios de código, ejecución segura de comandos bash del agente y la firma criptográfica de solicitudes.

## 🚀 Características Principales

- **Gestor de Worktrees**: Clonado y aislamiento de directorios de trabajo basados en commits utilizando `git worktree` para evitar colisiones en la rama activa.
- **Verificación Inteligente**: Compilación automática y ejecución de pruebas para evaluar la viabilidad de los parches propuestos.
- **Firma Criptográfica HMAC**: Validación de firmas de solicitudes mediante secreto compartido para evitar accesos no autorizados, con prevención de replay mediante timestamps y noce replay.
- **Compatibilidad con Systemd**: Archivo de servicio listo para configurar e iniciar en segundo plano en sistemas Linux.

## 🛠️ Instalación y Arranque

### 1. Dependencias del Sistema
Asegúrate de tener instalados los siguientes componentes en el host:
```bash
sudo apt-get update
sudo apt-get install -y python3-venv git
```

### 2. Entorno Virtual
Crea e instala las dependencias de Python del worker:
```bash
cd very-simplified-stack/cognito-worker/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Ejecución Directa (Desarrollo)
```bash
# Iniciar el servicio en el puerto por defecto (8001)
source venv/bin/activate
uvicorn worker_app.main:app --host 0.0.0.0 --port 8001
```

### 4. Configurar como Servicio Systemd (Producción)
Para ejecutar `cognito-worker` de forma persistente en segundo plano:

1. Modifica las rutas dentro de `cognito-worker.service` si es necesario.
2. Copia el archivo de servicio a systemd:
   ```bash
   sudo cp cognito-worker.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```
3. Inicia y habilita el servicio:
   ```bash
   sudo systemctl start cognito-worker
   sudo systemctl enable cognito-worker
   ```
4. Comprueba su estado:
   ```bash
   sudo systemctl status cognito-worker
   ```

## ⚙️ Configuración (Variables de Entorno)

Las siguientes variables de entorno controlan el comportamiento del worker:

- `COGNITO_WORKER_PORT`: Puerto de escucha del worker (default: `8001`).
- `COGNITO_WORKER_SECRET`: Clave secreta HMAC compartida para la validación de peticiones (debe coincidir con la del backend).
- `ALLOWED_ROOTS`: Lista de directorios del host donde el worker tiene permiso para crear worktrees.
- `WORKER_ID`: Identificador unificado de la instancia del worker.

## 🧪 Pruebas y Validación

Para correr la suite de tests del worker localmente:
```bash
source venv/bin/activate
PYTHONPATH=. pytest tests/
```
