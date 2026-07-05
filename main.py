import asyncio
import os

from dotenv import load_dotenv

from src.agent.core import Agent
from src.agent.llm import ClientConfig
from src.agent.prompts import SYSTEM_PROMPT
from src.utils.repl import run_repl


def main() -> None:
    load_dotenv()

    config = ClientConfig(
        model=os.environ.get("MODEL", "claude-sonnet-4-6"),
        api_key=os.environ.get("API_KEY", ""),
        base_url=os.environ.get("BASE_URL", ""),
        thinking=True,
        system_prompt=SYSTEM_PROMPT,
        stream=True,
    )

    agent = Agent(
        config,
        skills_dir="skills",
        on_tool_call=lambda name, inp: print(f"\n[tool: {name}] ", end="", flush=True),
        on_thinking=lambda t: print(f"\033[2m{t}\033[0m", end="", flush=True),
    )

    asyncio.run(run_repl(agent))


if __name__ == "__main__":
    main()
