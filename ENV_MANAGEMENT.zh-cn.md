# Gestión de Variables de Entorno
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/ENV_MANAGEMENT.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/ENV_MANAGEMENT.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/ENV_MANAGEMENT.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/ENV_MANAGEMENT.ca.md)


Este proyecto incluye varios scripts para gestionar las variables de entorno de forma inteligente y segura.

## 📁 Archivos

- **`.env`** - Archivo real con tus valores (NO commitear a git)
- **`.env.example`** - Plantilla con valores de ejemplo (SÍ commitear)
- **`generate_env_example.sh`** - Genera .env.example desde .env
- **`init_env.sh`** - Inicializa .env desde .env.example

## 🚀 Quick Start

### Primera vez (nuevo usuario del proyecto)

```bash
# 1. Inicializar archivo .env
./init_env.sh

# 2. El script generará automáticamente valores seguros y te preguntará por opcionales
# Sigue las instrucciones interactivas

# 3. Revisa y ajusta si es necesario
nano .env

# 4. Inicia los servicios
./start.sh --voice
```

### Modo automático (CI/CD o scripting)

```bash
# Genera .env con valores seguros sin interacción
./init_env.sh --auto

# Luego configura las variables opcionales manualmente
echo "TELEGRAM_BOT_TOKEN=tu_token" >> .env
echo "ZROK_AUTH_TOKEN=tu_token" >> .env
```

## 🔄 Workflow para Desarrolladores

### Actualizar .env.example después de cambiar .env

```bash
# Genera .env.example preservando valores útiles
./generate_env_example.sh

# Revisa los cambios
git diff .env.example

# Commitea si está bien
git add .env.example
git commit -m "Update .env.example with new variables"
```

### Sincronizar tu .env con nuevas variables

```bash
# Si alguien agregó variables nuevas al proyecto
git pull

# Actualiza tu .env con las nuevas variables
./init_env.sh
# Selecciona 'n' para no sobrescribir las existentes
# O manualmente:
cat .env.example >> .env
nano .env  # Elimina duplicados y configura las nuevas
```

## 🎯 Comportamiento de generate_env_example.sh

Este script es **inteligente** y preserva valores útiles:

### ✅ Variables que SE PRESERVAN:

1. **Valores predefinidos** (configuración técnica):
   ```bash
   WHISPER_MODEL=base.en
   REDIS_PORT=6379
   POSTGRES_USER_ID=999
   ```

2. **Valores de ejemplo** del .env.example existente:
   ```bash
   WEBHOOK_URL=http://localhost:5678
   ZROK_API_ENDPOINT=https://api.zrok.io
   ```

3. **Valores que parecen de documentación**:
   ```bash
   EXAMPLE_KEY=your_key_here
   TEST_VALUE=change_this
   ```

### 🔒 Variables que SE VACÍAN:

Variables sensibles (contienen estos patrones):
- `*PASSWORD*`
- `*SECRET*`
- `*KEY*` (excepto predefinidas)
- `*TOKEN*`
- `*AUTH*`
- `*JWT*`

```bash
# Antes en .env
POSTGRES_PASSWORD=mi_super_secreto_123

# Después en .env.example
POSTGRES_PASSWORD=
```

## 📋 Ejemplos de 使用

### Ejemplo 1: Primer setup del proyecto

```bash
# Clonar repositorio
git clone https://github.com/tu-org/ai-stack.git
cd ai-stack

# Hacer ejecutables los scripts
chmod +x *.sh

# Inicializar entorno
./init_env.sh

# Output esperado:
# ✅ Backup creado: .env.backup.20250101_120000
# ℹ️  Archivo .env creado desde .env.example
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Variable: N8N_ENCRYPTION_KEY
# Valor generado: 8f4e3c2b1a9d8e7f...
# ¿Usar este valor? (S/n/personalizar): s
# ✅ N8N_ENCRYPTION_KEY configurado
```

### Ejemplo 2: Añadir nueva variable al proyecto

```bash
# 1. Editar .env para testing
echo "NEW_FEATURE_API_KEY=test_value_123" >> .env

# 2. Testear que funciona
./start.sh

# 3. Generar .env.example actualizado
./generate_env_example.sh

# Output:
# 🔒 POSTGRES_PASSWORD (sensible - vaciado)
# ✓ WHISPER_MODEL (preservado)
# 🔒 NEW_FEATURE_API_KEY (sensible - vaciado)

# 4. Verificar resultado
cat .env.example | grep NEW_FEATURE
# NEW_FEATURE_API_KEY=

# 5. Commitear
git add .env.example
git commit -m "Add NEW_FEATURE_API_KEY configuration"
```

### Ejemplo 3: Agregar valor predefinido nuevo

```bash
# Editar generate_env_example.sh
# Añadir a EXAMPLE_VALUES:

declare -A EXAMPLE_VALUES=(
    ...
    ["NEW_SERVICE_PORT"]="8888"
    ["NEW_SERVICE_HOST"]="0.0.0.0"
)

# Regenerar
./generate_env_example.sh

# Ahora estos valores se preservarán siempre
```

## 🔐 Generación de Valores Seguros

El script `init_env.sh` usa estos métodos (en orden de preferencia):

1. **OpenSSL** (más común):
   ```bash
   openssl rand -hex 32
   ```

2. **Python** (si openssl no está disponible):
   ```python
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Bash** (fallback):
   ```bash
   cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1
   ```

### Generar manualmente

```bash
# Generar clave de 64 caracteres hex
openssl rand -hex 32

# Generar clave de 32 caracteres alfanuméricos
cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1
```

## 🛡️ Seguridad

### ✅ Buenas Prácticas

1. **NUNCA** commitear `.env` a git:
   ```bash
   # Verificar que está en .gitignore
   cat .gitignore | grep ".env"
   # Debería mostrar: .env
   ```

2. **SIEMPRE** rotar secrets en producción:
   ```bash
   # Antes de deploy
   ./init_env.sh --auto
   # Configura manualmente los servicios externos
   ```

3. **Backup** antes de regenerar:
   ```bash
   # Los scripts hacen backup automático, pero por si acaso:
   cp .env .env.backup.manual
   ```

4. **Revisar** cambios antes de commitear .env.example:
   ```bash
   git diff .env.example
   ```

### ⚠️ Qué NO hacer

- ❌ Commitear `.env` con valores reales
- ❌ Compartir `.env` por email/slack
- ❌ Usar valores de ejemplo en producción
- ❌ Reutilizar passwords entre servicios
- ❌ Hardcodear secrets en el código

## 🔍 Troubleshooting

### Problema: "No se generan valores seguros"

```bash
# Verificar que tienes las herramientas
which openssl
which python3

# Si no, instalar
# Ubuntu/Debian
sudo apt install openssl python3

# macOS
brew install openssl python3
```

### Problema: "Variables no se preservan en .env.example"

```bash
# Ver qué variables se están procesando
./generate_env_example.sh 2>&1 | grep "🔒\|✓\|∅"

# Si una variable debería preservarse pero se vacía:
# 1. Verifica que no contiene patrones sensibles (PASSWORD, SECRET, etc.)
# 2. O agrégala a EXAMPLE_VALUES en el script
```

### Problema: ".env sobreescrito accidentalmente"

```bash
# Restaurar desde backup automático
ls -la .env.backup.*
cp .env.backup.YYYYMMDD_HHMMSS .env

# O desde git si estaba commiteado (mal)
git checkout .env  # ¡No hagas esto si .env está en .gitignore!
```

## 📚 Referencia Rápida

### Variables Requeridas (deben tener valor)

```bash
# Seguridad n8n
N8N_ENCRYPTION_KEY=
N8N_USER_MANAGEMENT_JWT_SECRET=
N8N_AUTH_JWT_SECRET=
N8N_RUNNERS_AUTH_TOKEN=

# Bases de datos
POSTGRES_PASSWORD=
REDIS_PASSWORD=

# Para Forgejo
FORGEJO_DB_PASSWORD=
```

### Variables Opcionales

```bash
# Bot de Telegram
TELEGRAM_BOT_TOKEN=

# Túnel público
ZROK_AUTH_TOKEN=

# Búsqueda web
MCP_BRAVE_API_KEY=
```

### Variables con Valores Predefinidos (no cambiar)

```bash
WHISPER_MODEL=base.en
REDIS_PORT=6379
POSTGRES_PORT=5432
VOICE_GATEWAY_PORT=9000
```

## 🤝 Contribuir

Al añadir nuevas variables:

1. Añádelas a `.env.example` con:
   - Comentario descriptivo
   - Valor de ejemplo o vacío según corresponda
   - Sección apropiada

2. Si es un valor técnico (puerto, versión, etc.):
   ```bash
   # Añadir a EXAMPLE_VALUES en generate_env_example.sh
   ["NUEVA_VARIABLE"]="valor_por_defecto"
   ```

3. Si es sensible:
   ```bash
   # No hace falta nada, se detecta automáticamente
   # por los patrones: PASSWORD, SECRET, TOKEN, KEY, AUTH
   ```

4. Documentar en el README principal

## 📞 Soporte

Si tienes problemas:

1. Revisa los logs de los scripts
2. Verifica que `.env.example` está actualizado
3. Ejecuta `./debug_whisper.sh` para diagnóstico
4. Abre un issue en GitHub

---

**Última actualización**: 2025-01-01
