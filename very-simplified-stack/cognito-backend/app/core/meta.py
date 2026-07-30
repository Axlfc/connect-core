import inspect
import json
from typing import Any, Dict, Type, get_type_hints, get_origin, get_args
from pydantic import BaseModel
from app.services.unified_llm import UnifiedLLM

class NOOAMeta(type):
    """
    Metaclass that intercepts subclass initialization.
    Visible methods specified with elipsis (...) are automatically wrapped
    into UnifiedLLM completions enforcing return type constraints (contracts).
    """
    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: Dict[str, Any]) -> Any:
        # Scan methods in namespace
        for attr_name, attr_value in list(namespace.items()):
            if inspect.isfunction(attr_value) and not attr_name.startswith("__"):
                # Check if it has empty body (elipsis, single pass, or returns NotImplementedError/docstring-only)
                source = None
                try:
                    source = inspect.getsource(attr_value)
                except Exception:
                    pass

                is_generation_method = False
                if source:
                    # Look for signature ending with elipsis or pass
                    cleaned = source.strip().split("\n")
                    if len(cleaned) > 1:
                        last_line = cleaned[-1].strip()
                        if last_line in ("...", "pass", "raise NotImplementedError"):
                            is_generation_method = True
                    elif "..." in source or "pass" in source:
                        is_generation_method = True

                if is_generation_method:
                    # Wrap with automatic LLM executor
                    namespace[attr_name] = mcs._create_llm_wrapper(attr_value)

        return super().__new__(mcs, name, bases, namespace)

    @staticmethod
    def _create_llm_wrapper(original_func: Any) -> Any:
        import functools
        sig = inspect.signature(original_func)
        hints = get_type_hints(original_func)
        return_type = hints.get("return", str)
        docstring = inspect.getdoc(original_func) or "Generar respuesta para la tarea."

        @functools.wraps(original_func)
        async def wrapper(self, *args, **kwargs) -> Any:
            # Retrieve UnifiedLLM client associated with self (Agent)
            # or instantiate a default one
            llm_client = getattr(self, "llm_client", None)
            if not llm_client:
                llm_client = UnifiedLLM()

            # Compile parameters into user context prompt
            param_dict = {}
            bound = sig.bind(self, *args, **kwargs)
            bound.apply_defaults()
            for k, v in bound.arguments.items():
                if k != "self":
                    param_dict[k] = v

            prompt_content = (
                f"Método a ejecutar: {original_func.__name__}\n"
                f"Descripción del objetivo: {docstring}\n"
                f"Parámetros de entrada recibidos: {json.dumps(param_dict, default=str)}\n"
            )

            response_format = None
            # Check if return_type is Pydantic BaseModel to enforce structured output
            if isinstance(return_type, type) and issubclass(return_type, BaseModel):
                response_format = return_type

            raw_response = await llm_client.generate(prompt_content, response_format=response_format)

            # Enforce output contracts
            if response_format:
                try:
                    return response_format.model_validate_json(raw_response)
                except Exception as e:
                    # Try to find JSON block in output
                    try:
                        start_idx = raw_response.find("{")
                        end_idx = raw_response.rfind("}") + 1
                        if start_idx != -1 and end_idx != -1:
                            return response_format.model_validate_json(raw_response[start_idx:end_idx])
                    except Exception:
                        pass
                    raise ValueError(f"Contrato incumplido por el LLM para tipo {return_type.__name__}: {e}. Salida: {raw_response}")

            # Try to convert to typing primitives if specified
            if return_type == int:
                try:
                    return int(raw_response.strip())
                except ValueError:
                    pass
            elif return_type == float:
                try:
                    return float(raw_response.strip())
                except ValueError:
                    pass
            elif return_type == bool:
                return raw_response.strip().lower() in ("true", "yes", "1")

            return raw_response

        # Preserve function name, doc, annotations and other attributes
        return wrapper
