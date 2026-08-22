import json
from abc import ABC, abstractmethod
from typing import Any, Set, Optional, Dict
from pydantic import BaseModel, ValidationError
import jsonschema


class ToolContext(BaseModel):
    cwd: str
    trusted: bool
    protected_files: Set[str]


class ToolResult(BaseModel):
    output: str
    is_error: bool = False


def format_validation_error(
    tool_name: str,
    schema: dict[str, Any],
    arguments: dict[str, Any],
    error: Exception
) -> str:
    """
    Construct a structured, friendly error message for LLM tool call validation failures.
    """
    # Standardize tool display name (e.g., edit -> EditTool, EditTool -> EditTool)
    if not tool_name.endswith("Tool") and not (tool_name and tool_name[0].isupper()):
        formatted_tool_name = "".join(word.capitalize() for word in tool_name.split("_")) + "Tool"
    else:
        formatted_tool_name = tool_name

    failed_field = "desconocido"
    received_val: Any = None
    reason = "es inválido"

    if isinstance(error, jsonschema.exceptions.ValidationError):
        if error.validator == "required":
            missing = [f for f in error.validator_value if f not in arguments]
            if missing:
                failed_field = missing[0]
            elif error.message and "'" in error.message:
                failed_field = error.message.split("'")[1]
            received_val = arguments.get(failed_field, None)
            reason = "es obligatorio pero faltó"
        else:
            if error.path:
                failed_field = str(list(error.path)[0])
            elif error.json_path:
                clean_jp = error.json_path.lstrip("$.")
                if clean_jp:
                    failed_field = clean_jp
            received_val = error.instance
            if error.validator == "type":
                reason = f"debe ser de tipo '{error.validator_value}'"
            elif error.validator == "enum":
                reason = f"debe ser uno de {error.validator_value}"
            else:
                reason = f"no cumple con la regla '{error.validator}'"
    elif isinstance(error, ValidationError):
        errs = error.errors()
        if errs:
            first_err = errs[0]
            loc = first_err.get("loc", ())
            if loc:
                failed_field = str(loc[0])
            err_type = first_err.get("type", "")
            received_val = first_err.get("input", None)
            if "missing" in err_type:
                reason = "es obligatorio pero faltó"
                received_val = None
            elif "type" in err_type:
                reason = f"debe ser del tipo esperado pero se recibió {type(received_val).__name__}"
            elif "enum" in err_type:
                reason = "debe ser un valor permitido de la lista"
            else:
                reason = first_err.get("msg", "es inválido")

    props = schema.get("properties", {}) if schema else {}
    prop_info = props.get(failed_field, {})
    prop_desc = prop_info.get("description", "")

    # Spanish translation / guidance mapping for descriptions
    desc_map = {
        "Path to the file relative to cwd.": "proporciona la ruta del archivo relativa al directorio de trabajo.",
        "The exact string to be replaced.": "proporciona el texto exacto a reemplazar.",
        "The string to replace old_str with.": "proporciona el nuevo texto de reemplazo.",
        "The bash command to execute.": "proporciona el comando bash a ejecutar.",
        "File content to write.": "proporciona el contenido a escribir en el archivo.",
    }

    if prop_desc in desc_map:
        guidance = f"Por favor, {desc_map[prop_desc]}"
    elif prop_desc:
        guidance = f"Por favor, proporciona un valor válido para '{failed_field}' ({prop_desc})."
    else:
        guidance = f"Por favor, proporciona un valor válido para '{failed_field}'."

    return (
        f"Error de validación en '{formatted_tool_name}': "
        f"El campo '{failed_field}' {reason}. "
        f"Valor recibido: {received_val}. "
        f"{guidance}"
    )


class AgentTool(ABC):
    name: str
    description: str
    parameters_schema: dict[str, Any]  # Standard JSON Schema

    @abstractmethod
    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        ...

    async def validate_and_execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        """
        Validates arguments against parameters_schema and catches validation errors,
        returning a friendly ToolResult for LLMs.
        """
        if not isinstance(arguments, dict):
            arguments = {}

        schema = getattr(self, "parameters_schema", None) or {}
        if schema:
            try:
                jsonschema.validate(instance=arguments, schema=schema)
            except (jsonschema.exceptions.ValidationError, ValidationError) as ve:
                msg = format_validation_error(
                    tool_name=getattr(self, "name", self.__class__.__name__),
                    schema=schema,
                    arguments=arguments,
                    error=ve
                )
                return ToolResult(is_error=True, output=msg)

        try:
            return await self.execute(arguments, context)
        except (jsonschema.exceptions.ValidationError, ValidationError) as ve:
            msg = format_validation_error(
                tool_name=getattr(self, "name", self.__class__.__name__),
                schema=schema,
                arguments=arguments,
                error=ve
            )
            return ToolResult(is_error=True, output=msg)
