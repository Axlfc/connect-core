# AGENTS.md — cognito-backend

- No modifiques `app/services/backend_registry.py` ni `app/services/semantic_orchestrator.py` sin aprobación explícita del usuario.
- No modifiques `/v1/chat/completions` (comportamiento estable, usado en producción).
- Los tests de regresión de `/api/agent` y `/v1/chat/completions` deben seguir pasando.
