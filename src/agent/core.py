import asyncio
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Any
from .llm import LLMClient, Usage, ClientConfig
from .context import Context
from .tool import ToolRegistry, build_core_registry, ToolDef
from .skill_loder import SkillLoader
from .prompts import SYSTEM_PROMPT, MEMORY_TEMPLATE


def _load_memory() -> tuple[str, str]:
    """Return (essential_summary, full_content) from MEMORY.md.
    
    Essential = only the section ABOVE the first `---` separator line
    (after stripping YAML frontmatter). Contains user info only.
    Credentials, conventions, decisions stay in the full file for on-demand read.
    If MEMORY.md does not exist, a template is created automatically.
    """
    path = Path("MEMORY.md")
    if not path.exists():
        path.write_text(MEMORY_TEMPLATE, encoding="utf-8")
        print(f"[memory] 已创建 {path} 模板，请编辑填写凭据和偏好。")
    try:
        content = path.read_text(encoding="utf-8").strip()
    except Exception:
        return "", ""

    lines = content.split("\n")

    # Find the first `---` that acts as a section separator (skip frontmatter opening)
    sep_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "---" and i > 0:
            sep_idx = i
            break

    if sep_idx is not None:
        essential = "\n".join(lines[:sep_idx]).strip()
        # Strip YAML frontmatter delimiters
        if essential.startswith("---"):
            essential = essential[3:].strip()
    else:
        essential = content

    return essential, content


def _build_system_prompt(
    template_path: str = "prompts/system.md",
    skill_loader: SkillLoader | None = None,
    ) -> str:
    try:
        # breakpoint()
        template = Path(template_path).read_text(encoding="utf-8")
        
    except Exception:
        template = "You are a helpful assistant"
        
    # Skills
    if skill_loader:
        section = skill_loader.system_prompt_section()
        template = template.replace("{{SKILLS}}", section if section else "（无）")
    else:
        template = template.replace("{{SKILLS}}", "（无）")

    
    essential, _ = _load_memory()
    if essential:
        template += (
            f"{essential}\n"
        )
    
    return template

class Agent:
    def __init__(
        self, 
        config: ClientConfig,
        *,
        skills_dir: str = "skills",
        on_text: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
        on_tool_call: Callable[[str, dict], None] | None = None,
        ):
        self.skills_dir = skills_dir
        self.llm = LLMClient(config=config)
        self.context = Context()
        self.registry = build_core_registry()
        self.skill_loader = SkillLoader(skills_dir)
        if self.skill_loader.available():
            self._register_load_skill()
        
        self.on_text = on_text or (lambda t: print(t, end="", flush=True))
        self.on_thinking = on_thinking or self._default_on_thinking
        self.on_tool_call = on_tool_call or (lambda name, inp: print(f"\n[tool: {name}] ", end="", flush=True))
        
        self.llm.cfg.system_prompt = _build_system_prompt(skill_loader=self.skill_loader)
    
    def _register_load_skill(self) -> None:
        """Register the load_skill tool so the model can fetch full skill instructions."""
        schema = self.skill_loader.skill_tool_schema()

        async def handler(inp: dict) -> str:
            return self.skill_loader.load(inp["name"])

        self.registry.register(ToolDef(schema=schema, handler=handler))

    
    @staticmethod
    def _default_on_thinking(t: str) -> None:
        print(f"\033[2m{t}\033[0m", end="", flush=True)
    
    async def run(self, user_message: str):
        self.context.add_user(user_message)
        
        final_text: list[str] = []
        consecutive_errors = 0
        tools_schema = self.registry.schemas() if hasattr(self, "registry") else []
        # breakpoint()
        while True:
            """ check compact """
            turn_text: list[str] = []

            def _on_text(t: str) -> None:
                turn_text.append(t)
                self.on_text(t)

            def _on_thinking(t: str) -> None:
                self.on_thinking(t)
            try:
                ressponse = await self.llm.create(
                    self.context.to_list(),
                    tools = tools_schema,
                    on_text=_on_text,
                    on_thinking=_on_thinking
                )
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    return f"Error: too many consecutive LLM failures — {e}"
                await asyncio.sleep(2 ** consecutive_errors)
                continue
            
            content = ressponse.content
            self.context.add_assistant(content)
            tool_uses:list[dict] = []
            for block in content:
                btype = getattr(block, "type", None)
                if btype == "tool_use":
                    tool_uses.append(
                        {
                            "id": getattr(block, "id", None),
                            "name": getattr(block, "name", None),
                            "input": getattr(block, "input", {})
                        }
                    )
            
            if not tool_uses:
                final_text.extend(turn_text)
                break
            
            tool_results: list[dict] = []
            for tu in tool_uses:
                name = tu["name"]
                inp = tu["input"]
                tid = tu["id"]
                
                if self.on_tool_call:
                    self.on_tool_call(name, inp)
                try:
                    result = await self.registry.dispatch(name, inp)
                    content_str = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                    tool_results.append({
                        "tool_use_id": tid,
                        "type": "tool_result",
                        "content": content_str,
                    })
                except Exception as e:
                    tool_results.append({
                        "tool_use_id": tid,
                        "type": "tool_result",
                        "content": f"Tool error: {e}",
                        "is_error": True,
                    })

            self.context.add_tool_results(tool_results)
