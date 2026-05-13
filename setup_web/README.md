# Asistente web de configuración — cognito-stack
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/setup_web/README.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/setup_web/README.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/setup_web/README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/setup_web/README.zh-cn.md)


Pequeño servicio Flask que expone una UI en `http://localhost:9999/setup` para generar un archivo `.env` con claves seguras y seleccionar el perfil de hardware.

Instrucciones rápidas:

```bash
# crear y activar un entorno virtual (opcional pero recomendado)
python3 -m venv .venv
source .venv/bin/activate

pip install -r setup_web/requirements.txt

# arrancar la app (válido en desarrollo)
python setup_web/app.py

# abrir http://localhost:9999/setup en el navegador
```

El servicio leerá `.env.example` si existe y rellenará valores vacíos con claves/contraseñas seguras.
