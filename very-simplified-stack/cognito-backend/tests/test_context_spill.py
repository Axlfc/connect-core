import time
import pytest
from pathlib import Path
from app.core.context_spill import SpillManager, spill_large_content, clean_old_spills
from app.core.tools.query_spill_tool import QuerySpillTool
from app.core.tools.read_spill_tool import ReadSpillTool
from app.core.tools.read_tool import ReadTool
from app.core.tools.base import ToolContext

@pytest.fixture
def temp_spill_dir(tmp_path):
    spill_dir = tmp_path / "spill"
    spill_dir.mkdir()
    return spill_dir

@pytest.fixture
def spill_manager(temp_spill_dir):
    return SpillManager(
        spill_dir=temp_spill_dir,
        token_threshold=100,  # lower threshold for testing
        ttl_seconds=3600,
        max_storage_bytes=10000,
    )

def test_spill_large_content_below_threshold(temp_spill_dir):
    short_text = "This is a short text."
    result = spill_large_content(short_text, threshold=4000, spill_dir=temp_spill_dir)
    assert result == short_text

def test_spill_large_content_above_threshold(temp_spill_dir):
    large_text = "A" * 5000
    result = spill_large_content(large_text, threshold=4000, spill_dir=temp_spill_dir)
    assert "[SPILL: contenido almacenado en spill_" in result
    assert "Usa la herramienta 'read_spill' para consultarlo.]" in result

    # Check file was written to spill_dir
    spill_files = list(temp_spill_dir.glob("spill_*.txt"))
    assert len(spill_files) == 1
    assert spill_files[0].read_text(encoding="utf-8") == large_text

def test_clean_old_spills_pathlib(temp_spill_dir):
    old_file = temp_spill_dir / "old_spill.txt"
    old_file.write_text("old content", encoding="utf-8")

    import os
    old_mtime = time.time() - 100
    os.utime(old_file, (old_mtime, old_mtime))

    deleted = clean_old_spills(spill_dir=temp_spill_dir, ttl_seconds=50)
    assert deleted == 1
    assert not old_file.exists()

def test_spill_manager_should_spill(spill_manager):
    small_text = "Hello world"
    large_text = "word " * 500  # approx 500 tokens (> 100 limit)

    assert not spill_manager.should_spill(small_text)
    assert spill_manager.should_spill(large_text)

def test_spill_manager_save_and_read(spill_manager):
    content = "Line 1: Alpha\nLine 2: Beta\nLine 3: Gamma\nLine 4: Delta\nLine 5: Epsilon"
    spill_id = spill_manager.spill(content)

    assert spill_id.startswith("spill_")
    assert spill_manager.read_spill(spill_id) == content

def test_spill_manager_query_line_range(spill_manager):
    lines = [f"Line {i}: Content" for i in range(1, 21)]
    content = "\n".join(lines)
    spill_id = spill_manager.spill(content)

    res = spill_manager.query_spill(spill_id, line_range=[2, 4])
    assert "Line 2: Content" in res
    assert "Line 3: Content" in res
    assert "Line 4: Content" in res
    assert "Line 1: Content" not in res
    assert "Line 5: Content" not in res

def test_spill_manager_query_keyword(spill_manager):
    content = "apple pie\nbanana split\ncherry tart\napple crumble"
    spill_id = spill_manager.spill(content)

    res = spill_manager.query_spill(spill_id, query="apple")
    assert "Found 2 matching line(s)" in res
    assert "1: apple pie" in res
    assert "4: apple crumble" in res
    assert "banana split" not in res

def test_spill_manager_cleanup_ttl(temp_spill_dir):
    sm = SpillManager(spill_dir=temp_spill_dir, ttl_seconds=1)
    spill_id = sm.spill("content")
    spill_file = sm.get_spill_path(spill_id)
    assert spill_file.exists()

    # Artificially age the file
    old_mtime = time.time() - 10
    import os
    os.utime(spill_file, (old_mtime, old_mtime))

    deleted = sm.cleanup()
    assert deleted == 1
    assert not spill_file.exists()

def test_spill_manager_cleanup_max_bytes(temp_spill_dir):
    sm = SpillManager(spill_dir=temp_spill_dir, ttl_seconds=3600, max_storage_bytes=50)
    # Write two spill files of size ~40 bytes each
    id1 = sm.spill("A" * 40)
    time.sleep(0.05)
    id2 = sm.spill("B" * 40)

    # Calling spill or cleanup should remove oldest file (id1)
    sm.cleanup()

    assert sm.read_spill(id1) is None
    assert sm.read_spill(id2) == "B" * 40

@pytest.mark.asyncio
async def test_read_spill_tool(temp_spill_dir):
    tool = ReadSpillTool(spill_dir=temp_spill_dir)
    content = "Line 1: Alpha\nLine 2: Beta\nLine 3: Gamma\nLine 4: Delta"
    spill_ref = spill_large_content(content, threshold=10, spill_dir=temp_spill_dir)
    spill_id = spill_ref.split("en ")[1].split(".")[0]

    ctx = ToolContext(cwd="/tmp", trusted=True, protected_files=set())

    # Read full content
    res_full = await tool.execute({"spill_id": spill_id}, ctx)
    assert not res_full.is_error
    assert res_full.output == content

    # Read line range
    res_range = await tool.execute({"spill_id": spill_id, "line_range": [2, 3]}, ctx)
    assert not res_range.is_error
    assert res_range.output == "Line 2: Beta\nLine 3: Gamma"

    # Read start_line/end_line
    res_lines = await tool.execute({"spill_id": spill_id, "start_line": 1, "end_line": 2}, ctx)
    assert not res_lines.is_error
    assert res_lines.output == "Line 1: Alpha\nLine 2: Beta"

    # Query with invalid spill_id
    res_err = await tool.execute({"spill_id": "spill_nonexistent"}, ctx)
    assert res_err.is_error
    assert "no encontrado o expirado" in res_err.output

@pytest.mark.asyncio
async def test_query_spill_tool(spill_manager):
    tool = QuerySpillTool(spill_manager=spill_manager)
    content = "First line\nSecond line\nThird line"
    spill_id = spill_manager.spill(content)

    ctx = ToolContext(cwd="/tmp", trusted=True, protected_files=set())

    # Query with line_range
    res = await tool.execute({"spill_id": spill_id, "line_range": [2, 2]}, ctx)
    assert not res.is_error
    assert "2: Second line" in res.output

    # Query with invalid spill_id
    res_err = await tool.execute({"spill_id": "spill_nonexistent"}, ctx)
    assert res_err.is_error
    assert "was not found or has expired" in res_err.output

@pytest.mark.asyncio
async def test_read_tool_spill_integration(tmp_path, temp_spill_dir):
    spill_mgr = SpillManager(spill_dir=temp_spill_dir, token_threshold=50)
    read_tool = ReadTool(spill_manager=spill_mgr)

    ctx = ToolContext(cwd=str(tmp_path), trusted=True, protected_files=set())

    # Small file
    small_file = tmp_path / "small.txt"
    small_file.write_text("Hello small world", encoding="utf-8")
    res_small = await read_tool.execute({"path": "small.txt"}, ctx)
    assert not res_small.is_error
    assert res_small.output == "Hello small world"

    # Large file (> threshold)
    large_file = tmp_path / "large.txt"
    large_content = "word " * 1000
    large_file.write_text(large_content, encoding="utf-8")
    res_large = await read_tool.execute({"path": "large.txt"}, ctx)

    assert not res_large.is_error
    assert "[SPILL: contenido almacenado en spill_" in res_large.output
    assert "Usa la herramienta 'read_spill' para consultarlo.]" in res_large.output
