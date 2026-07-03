from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Any
from .llm import LLMClient, Usage, ClientConfig
from .context import Context
from .tools import ToolRegistry, build_core_registry
from .skill_loder import SkillLoader


def _build_system_prompt(
    template_path: str = "prompts/system.md",
    skill_loader: SkillLoader | None = None,
    ) -> str:
    try:
        # breakpoint()
        template = Path(template_path).read_text(encoding="utf-8")
        
    except Exception:
        template = "You are a helpful assistant"
        
    if skill_loader:
        pass
    
    return template

class Agent:
    def __init__(
        self, 
        config: ClientConfig,
        *,
        skills_dir: str = "skills",
        on_text: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
        ):
        self.skills_dir = skills_dir
        self.llm = LLMClient(config=config)
        self.context = Context()
        self.registry = build_core_registry()
        self.skill_loader = SkillLoader(skills_dir)
        self.on_text = on_text or (lambda t: print(t, end="", flush=True))
        self.on_thinking = on_thinking or self._default_on_thinking
        
        self.llm.cfg.system_prompt = _build_system_prompt(skill_loader=self.skill_loader)
    
    @staticmethod
    def _default_on_thinking(t: str) -> None:
        print(f"\033[2m{t}\033[0m", end="", flush=True)
    
    async def run(self, user_message: str):
        self.context.add_user(user_message)
        
        final_text: list[str] = []
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
                
            ressponse = await self.llm.create(
                self.context.to_list(),
                tools = tools_schema,
                on_text=_on_text,
                on_thinking=_on_thinking
            )
            
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
            
                result = await self.registry.dispatch(name, inp)
                content_str = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                tool_results.append({
                    "tool_use_id": tid,
                    "type": "tool_result",
                    "content": content_str,
                })
            
            self.context.add_tool_results(tool_results)
            
            breakpoint()
        
                
                