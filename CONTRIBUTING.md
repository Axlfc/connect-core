# Contributing to cognito-stack 🤝
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/CONTRIBUTING.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/CONTRIBUTING.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/CONTRIBUTING.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/CONTRIBUTING.zh-cn.md)


¡Gracias por tu interés en contribuir a cognito-stack! Este documento proporciona las pautas para contribuir al proyecto.

## Tabla de contenidos

- [Código de conducta](#código-de-conducta)
- [¿Cómo contribuir?](#cómo-contribuir)
- [Reportar bugs](#reportar-bugs)
- [Sugerir mejoras](#sugerir-mejoras)
- [Pull Requests](#pull-requests)
- [Estándares de código](#estándares-de-código)
- [Validación local](#validación-local)
- [Commit conventions](#commit-conventions)

---

## Código de conducta

### Nuestra promesa

Nos comprometemos a proporcionar un entorno abierto y acogedor para todos, independientemente de:
- Edad, tamaño corporal, capacidad/discapacidad
- Etnia, identidad y expresión de género
- Nivel de experiencia, educación
- Situación socioeconómica

### Nuestros estándares

Comportamientos que contribuyen a crear un entorno positivo:
- ✅ Usar lenguaje inclusivo y acogedor
- ✅ Ser respetuoso con los puntos de vista diferentes
- ✅ Aceptar críticas constructivas
- ✅ Enfocarse en lo mejor para la comunidad
- ✅ Mostrar empatía hacia otros miembros

Comportamientos inaceptables:
- ❌ Lenguaje o imágenes sexuales
- ❌ Trolling, comentarios insultantes o ataques personales
- ❌ Acoso público o privado
- ❌ Publicar información privada sin consentimiento
- ❌ Otra conducta inapropiada

---

## ¿Cómo contribuir?

### Requisitos previos

- Git instalado (`git --version`)
- Docker & Docker Compose (`docker --version`, `docker compose version`)
- Bash 4.0+ (`bash --version`)
- Cuenta GitHub

### Workflow de contribución

1. **Fork el repositorio**
   ```bash
   # En GitHub, haz clic en "Fork"
   # Luego clona tu fork
   git clone https://github.com/TU_USUARIO/cognito-stack.git
   cd cognito-stack
   ```

2. **Crea una rama para tu feature**
   ```bash
   git checkout -b feature/descripcion-clara
   # o para bugs:
   git checkout -b fix/descripcion-del-bug
   ```

3. **Realiza cambios**
   - Edita archivos necesarios
   - Mantén commits atómicos y con mensajes claros
   - Valida localmente (ver [Validación local](#validación-local))

4. **Push a tu fork**
   ```bash
   git push origin feature/descripcion-clara
   ```

5. **Abre un Pull Request**
   - Haz clic en "New Pull Request" en GitHub
   - Completa el template de PR
   - Espera review

---

## Reportar bugs

### Antes de reportar

- ✅ Verifica que no exista un issue similar
- ✅ Actualiza al código más reciente (`git pull origin master`)
- ✅ Reproduce el bug con el código actual
- ✅ Recopila información de debugging

### Cómo reportar

**Abre un issue** con los siguientes detalles:

```markdown
## Descripción
Breve descripción del bug

## Pasos para reproducir
1. ...
2. ...
3. ...

## Comportamiento actual
¿Qué sucedió?

## Comportamiento esperado
¿Qué debería suceder?

## Información del sistema
- OS: [ej: Ubuntu 22.04]
- Docker version: [ej: 24.0.0]
- Profile: [cpu/gpu-nvidia/gpu-amd]

## Logs
```
<logs relevantes aquí>
```

## Información adicional
Cualquier contexto adicional
```

---

## Sugerir mejoras

### Antes de sugerir

- ✅ Lee la documentación
- ✅ Busca sugerencias similares
- ✅ Considera el alcance del proyecto

### Template de sugerencia

```markdown
## Descripción breve
Una línea describiendo la mejora

## Problema que resuelve
¿Qué problema de usuario resuelve esto?

## Solución propuesta
Descripción de la mejora

## Beneficios
- Beneficio 1
- Beneficio 2

## Ejemplos de implementación
Pseudocódigo o ejemplos si aplica

## Alternativas consideradas
Otras soluciones evaluadas
```

---

## Pull Requests

### Checklist antes de abrir PR

- [ ] Mi código sigue los estándares de código del proyecto
- [ ] He actualizado la documentación
- [ ] Mis commits tienen mensajes claros y descriptivos
- [ ] He validado localmente con `scripts/validate.sh`
- [ ] He testeado con `scripts/smoke-test.sh`
- [ ] No contiene código "en construcción" o temporal
- [ ] No añade dependencias innecesarias

### Proceso de review

1. **Validación automática** (GitHub Actions)
   - YAML validation
   - Shell linting
   - Dockerfile linting
   - Docker Compose validation
   - Security checks

2. **Review manual**
   - Revisión de código
   - Evaluación de cambios
   - Solicitud de cambios si es necesario

3. **Merge**
   - Aprobación del maintainer
   - Squash & merge a master
   - CI/CD deploys cambios

### Template de PR

```markdown
## Descripción
Breve descripción de los cambios

## Relacionado con
- Closes #123
- Fixes #456

## Tipo de cambio
- [ ] Bug fix
- [ ] Nueva feature
- [ ] Cambio de documentación
- [ ] Refactoring

## Cambios realizados
- Cambio 1
- Cambio 2
- Cambio 3

## Testing realizado
Describe cómo testeaste los cambios

## Screenshots (si aplica)
Añade screenshots si hay cambios visuales

## Notas adicionales
Cualquier información adicional para los reviewers
```

---

## Estándares de código

### Shell Scripts (.sh)

```bash
#!/bin/bash
set -e  # Exit on error

# Usar comentarios descriptivos
# Variables en MAYUSCULAS
CONFIG_FILE="/path/to/file"

# Funciones con nombres descriptivos
print_info() {
    echo "ℹ️ $1"
}

# Validación de entrada
if [ -z "$1" ]; then
    echo "Error: Falta parametro"
    exit 1
fi

# Usar comillas para variables
echo "Mensaje: $CONFIG_FILE"
```

**Herramienta:** `shellcheck`
```bash
shellcheck script.sh
```

### Dockerfiles

```dockerfile
FROM base-image:version

LABEL maintainer="maintainer@example.com"
LABEL description="Clear description"

# Usar comentarios para secciones
USER root

# Combinar RUN cuando sea posible
RUN apt-get update && \
    apt-get install -y \
    package1 \
    package2 && \
    rm -rf /var/lib/apt/lists/*

# Exponer puertos explícitamente
EXPOSE 5678

# Definir volúmenes
VOLUME ["/data"]

# Usuario no-root
USER appuser

ENTRYPOINT ["./entrypoint.sh"]
CMD ["start"]
```

**Herramienta:** `hadolint`
```bash
hadolint Dockerfile
```

### YAML (docker-compose.yml)

```yaml
# Indentación de 2 espacios
version: "3.8"

services:
  service-name:
    image: image:version
    
    # Organización lógica
    container_name: service-name
    restart: unless-stopped
    
    # Variables de entorno primero
    environment:
      - VAR_NAME=value
    
    # Puertos
    ports:
      - "5678:5678"
    
    # Volúmenes
    volumes:
      - volume-name:/path
    
    # Healthcheck
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5678"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  network-name:
    driver: bridge
```

### JSON (n8n-task-runners.json)

```json
{
  "task-runners": [
    {
      "runner-type": "python",
      "command": "/usr/bin/python3",
      "args": ["--flag", "value"],
      "health-check-server-port": "5682"
    }
  ]
}
```

**Validar con:** `python -m json.tool n8n-task-runners.json`

### Documentación (Markdown)

- ✅ Títulos jerárquicos claros
- ✅ Ejemplos de código en bloques
- ✅ Enlaces internos a archivos
- ✅ Tabla de contenidos para documentos largos
- ✅ Notas destacadas con blockquotes
- ✅ Listas estructuradas

```markdown
# Título Principal

## Subtítulo

### Subsubtítulo

**Texto en negrita** y *en itálica*

> Nota o cita importante

### Ejemplo de código
\`\`\`bash
# Bash code
echo "Hello"
\`\`\`

- Punto 1
- Punto 2
  - Subpunto 2a
```

---

## Validación local

### 1. Script de validación general

```bash
# Ejecuta todas las comprobaciones
./scripts/validate.sh

# Salida esperada:
# ✓ Validaciones pasadas
# ⚠ Warnings (no bloquea)
# ✗ Errores (bloquea)
```

### 2. Smoke test

```bash
# Prueba rápida del stack (requiere Docker)
./scripts/smoke-test.sh          # Usa profile CPU
./scripts/smoke-test.sh gpu-nvidia  # Usa GPU NVIDIA
./scripts/smoke-test.sh gpu-amd     # Usa GPU AMD

# Comprueba:
# - Inicio de servicios
# - Health checks
# - Disponibilidad de APIs
```

### 3. Linting manual

```bash
# Shell
shellcheck *.sh

# Dockerfiles
hadolint Dockerfile*

# YAML
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"

# JSON
python3 -m json.tool n8n-task-runners.json

# Markdown
markdownlint *.md
```

### 4. Validación de Docker Compose

```bash
# Verificar sintaxis
docker compose config --quiet

# Listar servicios
docker compose config | grep "^  [a-z]"

# Simular inicio (sin pull)
docker compose --profile cpu config --quiet
```

---

## Commit conventions

### Formato de mensaje

```
<tipo>(<alcance>): <asunto>

<descripción>

<footer>
```

### Tipos de commit

- `feat:` Nueva funcionalidad
- `fix:` Corrección de bug
- `docs:` Cambios de documentación
- `style:` Cambios de formato (no lógica)
- `refactor:` Refactorización sin cambio funcional
- `test:` Cambios en tests/validación
- `ci:` Cambios en CI/CD
- `chore:` Cambios de build, dependencias, etc

### Ejemplos

```bash
# Feature
git commit -m "feat(n8n): agregar soporte para runners paralelos"

# Bug fix
git commit -m "fix(docker-compose): corregir puerto de Ollama"

# Documentation
git commit -m "docs: actualizar guía de instalación"

# Con descripción
git commit -m "feat(comfyui): agregar soporte para custom nodes

- Instala git durante build
- Clona repositorio de custom nodes
- Configura rutas correctas

Closes #42"
```

---

## Preguntas frecuentes

### ¿Cuál es el proceso de release?

1. Cambios en master van a production
2. GitHub Actions valida y construye imágenes
3. Imágenes se publican en GHCR
4. Tags semánticos para releases

### ¿Cómo reporto un vulnerability?

**NO** abras un issue público. Contáctanos privadamente:
- Email: [maintainer email si disponible]
- GitHub Security Advisory: Usa la opción "Report a vulnerability"

### ¿Cuánto tiempo tarda el review?

- Bugs críticos: 24-48 horas
- Features: 3-7 días
- Documentación: 1-3 días
- Depende de complejidad y disponibilidad

### ¿Puedo sugerir nuevas dependencias?

Sí, pero:
- Justifica por qué es necesaria
- Considera alternativas ligeras
- Actualiza Dockerfiles correspondientes
- Añade a documentación

---

## Recursos útiles

- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Markdown Guide](https://www.markdownguide.org/)
- [ShellCheck Wiki](https://www.shellcheck.net/wiki/)
- [Dockerfile Best Practices](https://docs.docker.com/develop/dev-best-practices/)

---

## Reconocimiento

¡Gracias por contribuir a cognito-stack! Cada contribución, sin importar su tamaño, ayuda a mejorar el proyecto.

Si tienes preguntas, no dudes en abrir un issue de discussion o contactar a los maintainers.

---

<div align="center">

**¡Esperamos tu contribución! ❤️**

</div>
