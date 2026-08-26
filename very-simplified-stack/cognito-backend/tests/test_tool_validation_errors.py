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


@pytest.mark.parametrize(
    "tool_cls, invalid_args, expected_error_substr",
    [
        # ReadTool: missing path
        ("ReadTool", {}, "El campo 'path' es obligatorio pero faltó"),
        # ReadTool: incorrect type for path
        ("ReadTool", {"path": 12345}, "El campo 'path' debe ser de tipo 'string'"),
        # WriteTool: missing content
        ("WriteTool", {"path": "file.txt"}, "El campo 'content' es obligatorio pero faltó"),
        # WriteTool: incorrect type for content
        ("WriteTool", {"path": "file.txt", "content": 999}, "El campo 'content' debe ser de tipo 'string'"),
        # BashTool: missing command
        ("BashTool", {}, "El campo 'command' es obligatorio pero faltó"),
        # BashTool: incorrect type for user_approved
        ("BashTool", {"command": "ls", "user_approved": "yes"}, "El campo 'user_approved' debe ser de tipo 'boolean'"),
        # EditTool: missing old_str
        ("EditTool", {"path": "file.txt", "new_str": "new"}, "El campo 'old_str' es obligatorio pero faltó"),
    ],
)
@pytest.mark.asyncio
async def test_local_tools_reject_invalid_arguments_fail_fast(tool_cls, invalid_args, expected_error_substr):
    from app.core.tools.read_tool import ReadTool
    from app.core.tools.write_tool import WriteTool
    from app.core.tools.bash_tool import BashTool
    from app.core.tools.edit_tool import EditTool

    tools_map = {
        "ReadTool": ReadTool,
        "WriteTool": WriteTool,
        "BashTool": BashTool,
        "EditTool": EditTool,
    }

    tool = tools_map[tool_cls]()
    ctx = ToolContext(cwd="/tmp", trusted=True, protected_files=set())

    res = await tool.validate_and_execute(invalid_args, ctx)

    assert res.is_error is True
    assert expected_error_substr in res.output


@pytest.mark.parametrize(
    "mcp_tool_name, invalid_args, expected_error_substr",
    [
        ("execute_agent_task", {}, "El campo 'prompt' es obligatorio pero faltó"),
        ("execute_agent_task", {"prompt": 123}, "El campo 'prompt' debe ser de tipo 'string'"),
        ("get_session_status", {}, "El campo 'session_id' es obligatorio pero faltó"),
        ("get_session_status", {"session_id": 999}, "El campo 'session_id' debe ser de tipo 'string'"),
        ("generate_with_llm", {}, "El campo 'prompt' es obligatorio pero faltó"),
    ],
)
@pytest.mark.asyncio
async def test_mcp_tools_reject_invalid_arguments_fail_fast(mcp_tool_name, invalid_args, expected_error_substr):
    from app.services.mcp_server import mcp_server

    res = await mcp_server.call_tool(
        name=mcp_tool_name,
        arguments=invalid_args,
        origin="test",
        correlation_id="corr-val-1",
        execution_depth=1,
    )

    assert res.get("is_error") is True
    assert expected_error_substr in res.get("output", "")


@pytest.mark.asyncio
async def test_valid_arguments_pass_local_and_mcp_tools(tmp_path):
    from app.core.tools.write_tool import WriteTool
    from app.core.tools.read_tool import ReadTool
    from app.services.mcp_server import mcp_server

    ctx = ToolContext(cwd=str(tmp_path), trusted=True, protected_files=set())

    # Local write valid
    write_tool = WriteTool()
    res_write = await write_tool.validate_and_execute({"path": "sample.txt", "content": "hello world"}, ctx)
    assert res_write.is_error is False

    # Local read valid
    read_tool = ReadTool()
    res_read = await read_tool.validate_and_execute({"path": "sample.txt"}, ctx)
    assert res_read.is_error is False
    assert "hello world" in res_read.output

    # MCP tool valid arguments
    res_mcp = await mcp_server.call_tool(
        name="cognito_architecture_context",
        arguments={},
        origin="test",
        correlation_id="corr-val-2",
        execution_depth=1,
    )
    assert res_mcp.get("is_error") is not True
    assert "architecture" in res_mcp
