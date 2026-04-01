import pytest
from server.tools import tool_cmd, tool_shell

@pytest.mark.asyncio
async def test_tool_shell_blacklist():
    res = await tool_shell({"command": "rm -rf /"})
    assert "Blocked for safety" in res

@pytest.mark.asyncio
async def test_tool_shell_success():
    # Cross platform safe command
    res = await tool_shell({"command": "echo hello"})
    assert "STDOUT:" in res
    assert "hello" in res

@pytest.mark.asyncio
async def test_tool_cmd_success():
    res = await tool_cmd({"code": "print('world')"})
    assert "world" in res
