# Cognito System Prompt Versioning & Evaluation Suite

Este directorio contiene el framework de versionado y la suite de evaluación para el **System Prompt** de Cognito (`app/core/system_prompt.py`).

---

## 📐 Estructura de archivos

```text
cognito-backend/app/core/prompts/
└── system_prompt.v1.toml          # Definición TOML del prompt base (v1)

evals/system_prompt/
├── dataset/
│   └── cases.jsonl                # Dataset de casos de prueba / eval cases
├── schemas.py                     # Modelos Pydantic para los casos y resultados
├── evaluator.py                   # Ejecutor de evaluaciones y cálculo de métricas
├── __main__.py                    # CLI para correr evals y mostrar reportes
├── eval_results.json              # Últimos resultados generados
└── README.md                      # Documentación del flujo de trabajo
```

---

## 🔄 Flujo de Trabajo para Proponer Cambios en el System Prompt

Para modificar o actualizar el system prompt de Cognito, se debe seguir la siguiente metodología paso a paso:

### 1. Crear una nueva versión del Prompt
En lugar de modificar un archivo existente directamente en producción sin rastro:
1. Copia el archivo TOML de la versión actual a uno nuevo en `very-simplified-stack/cognito-backend/app/core/prompts/`.
   - Ejemplo: `system_prompt.v1.1.toml` o `system_prompt.v2.toml`.
2. Actualiza la cabecera del archivo TOML:
   ```toml
   version = "1.1.0"
   description = "COGNITO_SYSTEM_PROMPT v1.1.0 (Ejemplo de actualización)"
   prompt = """..."""
   ```

### 2. Ejecutar la Suite de Evaluación contra la Nueva Versión
Ejecuta la suite de evals indicando la versión que estás probando:

```bash
PYTHONPATH=very-simplified-stack/cognito-backend:very-simplified-stack python3 -m evals.system_prompt run --version v1.1
```

O para volver a validar la versión v1 por defecto:
```bash
PYTHONPATH=very-simplified-stack/cognito-backend:very-simplified-stack python3 -m evals.system_prompt run --version v1
```

### 3. Verificar el Reporte de Evaluación
La suite generará un reporte formateado en la terminal y guardará `eval_results.json`.
Asegúrate de que:
- El **Pass Rate** sea del 100% (o que las métricas requeridas se cumplan sin regresiones).
- Ninguna regla obligatoria (`required_keywords`, límites de seguridad o tono) haya fallado.

### 4. Documentar los Resultados en el PR
Incluye en la descripción del Pull Request:
1. La versión introducida (ej. `v1.1.0`).
2. El motivo del cambio (ej. incorporación de reglas de guardrails de COG-007).
3. La salida formateada de la suite de evals (`python3 -m evals.system_prompt run --version ...`).

### 5. Actualizar la Versión por Defecto (si aplica)
Si la nueva versión pasa las evaluaciones y es aprobada en la revisión de código, actualiza `DEFAULT_VERSION` en `very-simplified-stack/cognito-backend/app/core/system_prompt.py` o configura la variable de entorno `COGNITO_SYSTEM_PROMPT_VERSION`.
