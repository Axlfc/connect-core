import pytest
from pydantic import BaseModel, Field, ValidationError
from app.core.tools.base import AgentTool, ToolContext, ToolResult, format_validation_error

class DummyTool(AgentTool):
    name = "edit"
    description = "Edit a file by replacing old_str with new_str."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file relative to cwd."},
            "old_str": {"type": "string", "description": "The exact string to be replaced."},
            "new_str": {"type": "string", "description": "The string to replace old_str with."},
            "mode": {"type": "string", "enum": ["replace", "append"]},
        },
        "required": ["path", "old_str", "new_str"],
    }

    async def execute(self, arguments, context):
        if arguments.get("path") == "raise_pydantic":
            class DummyModel(BaseModel):
                old_str: str = Field(...)

            DummyModel()  # Will raise pydantic ValidationError
        return ToolResult(output="success")


@pytest.mark.asyncio
async def test_missing_required_argument():
    tool = DummyTool()
    ctx = ToolContext(cwd="/tmp", trusted=True, protected_files=set())
    # Missing old_str
    res = await tool.validate_and_execute({"path": "test.txt", "new_str": "new"}, ctx)

    assert res.is_error is True
    assert "Error de validación en 'EditTool'" in res.output
    assert "El campo 'old_str' es obligatorio pero faltó" in res.output
    assert "Valor recibido: None" in res.output
    assert "Por favor, proporciona el texto exacto a reemplazar." in res.output


@pytest.mark.asyncio
async def test_invalid_type_argument():
    tool = DummyTool()
    ctx = ToolContext(cwd="/tmp", trusted=True, protected_files=set())
    # old_str should be string, got int
    res = await tool.validate_and_execute({"path": "test.txt", "old_str": 123, "new_str": "new"}, ctx)

    assert res.is_error is True
    assert "Error de validación en 'EditTool'" in res.output
    assert "El campo 'old_str' debe ser de tipo 'string'" in res.output
    assert "Valor recibido: 123" in res.output


@pytest.mark.asyncio
async def test_invalid_enum_argument():
    tool = DummyTool()
    ctx = ToolContext(cwd="/tmp", trusted=True, protected_files=set())
    # mode is invalid
    res = await tool.validate_and_execute(
        {"path": "test.txt", "old_str": "old", "new_str": "new", "mode": "invalid_mode"},
        ctx
    )

    assert res.is_error is True
    assert "Error de validación en 'EditTool'" in res.output
    assert "El campo 'mode' debe ser uno de ['replace', 'append']" in res.output


@pytest.mark.asyncio
async def test_pydantic_validation_error_handling():
    tool = DummyTool()
    ctx = ToolContext(cwd="/tmp", trusted=True, protected_files=set())
    res = await tool.validate_and_execute(
        {"path": "raise_pydantic", "old_str": "old", "new_str": "new"},
        ctx
    )

    assert res.is_error is True
    assert "Error de validación en 'EditTool'" in res.output
    assert "old_str" in res.output
