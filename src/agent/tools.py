import asyncio
import os
import signal
import tempfile

from dataclasses import dataclass
from typing import Callable, Any
from pathlib import Path


@dataclass
class ToolDef:
    schema: dict
    handler: Callable[..., Any]
    

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDef] = {}
    
    def register(self, tool:ToolDef) -> None:
        self._tools[tool.schema["name"]] = tool
    
    def schemas(self):
        return [i.schema for i in self._tools.values()]

    async def dispatch(self, name:str, _inp: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return "ERROR: tool is None"
        
        try:
            return await tool.handler(_inp)
        except Exception as e:
            return f"Error: {e}"
        
    def names(self) -> list[str]:
        return self._tools.keys()

BASH_SCHEMA = {
    "name": "bash",
    "description": (
        "Execute a shell command in bash and return the combined stdout/stderr output. "
        "Use for file operations (ls, grep, find, rg), running scripts, installing packages, "
        "and any other shell tasks. Output is capped at 2000 lines / 50 KB; when truncated "
        "the full output is written to a temp file whose path is included. "
        "The timeout parameter (default 30 s) kills the entire process tree on expiry. "
        "Do NOT use for reading files — use the read tool instead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute."},
            "timeout": {
                "type": "integer",
                "description": "Seconds before the command is killed (default 30, max 600).",
            },
        },
        "required": ["command"],
    },
}


BASH_MAX_LINES = 2000
BASH_MAX_BYTES = 50 * 1024
BASH_DEFAULT_TIMEOUT = 30           # seconds
TEMP_DIR = Path(tempfile.gettempdir())
async def _bash_handler(inp: dict) -> str:
    command = inp["command"]
    timeout = min(int(inp.get("timeout", BASH_DEFAULT_TIMEOUT)), 600)

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=os.environ.copy(),
        start_new_session=True,     # detached process group for clean kill
    )

    chunks: list[bytes] = []
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        chunks.append(stdout)
        rc = proc.returncode
    except asyncio.TimeoutError:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()
        return f"Error: command timed out after {timeout}s"

    output = b"".join(chunks).decode("utf-8", errors="replace")

    # Write full output to temp if needed
    tmp_label = ""
    lines = output.splitlines()
    if len(lines) > BASH_MAX_LINES or len(output.encode()) > BASH_MAX_BYTES:
        tmp = TEMP_DIR / f"bash_output_{proc.pid}.txt"
        tmp.write_text(output)
        tmp_label = str(tmp)

    # result = _truncate(output, BASH_MAX_LINES, BASH_MAX_BYTES, tmp_label)
    result = output
    if rc != 0:
        result += f"\n[exit code: {rc}]"
    return result

NOW_SCHEMA = {
    "name": "now",
    "description": "get current date and time",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": []
        }   
    
    }

async def _now_handler(inp:dict):
        await asyncio.sleep(0)
        print(inp.get("description"))
        return datetime.now().isoformat()
    
def build_core_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolDef(schema=NOW_SCHEMA,handler=_now_handler))
    # registry.register(ToolDef(schema=READ_SCHEMA, handler=_read_handler))
    registry.register(ToolDef(schema=BASH_SCHEMA, handler=_bash_handler))
    # registry.register(ToolDef(schema=EDIT_SCHEMA, handler=_edit_handler))
    # registry.register(ToolDef(schema=WRITE_SCHEMA, handler=_write_handler))
    return registry




if __name__ == "__main__":
    import asyncio
    from datetime import datetime
    
    NOW_SCHEMA = {
    "name": "now",
    "description": "get current date and time",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": []
        }   
    
    }
    
    async def _now_handler(inp:dict):
        await asyncio.sleep(0)
        print(inp.get("description"))
        return datetime.now().isoformat()
    
    registry = ToolRegistry()
    
    registry.register(
        ToolDef(
            schema=NOW_SCHEMA,
            handler=_now_handler
        )
    )
    
    result = asyncio.run(registry.dispatch(name="now",_inp=NOW_SCHEMA))
    print(result)