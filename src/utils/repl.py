from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style

from src.agent.core import Agent
from src.utils.completer import SlashCompleter


REPL_STYLE = Style.from_dict({
    "completion-menu.completion": "bg:#1e1e1e fg:#888888",
    "completion-menu.completion.current": "bg:#005f87 fg:#ffffff bold",
    "completion-menu.meta.completion": "bg:#1e1e1e fg:#5f8787",
    "completion-menu.meta.completion.current": "bg:#005f87 fg:#dddddd",
    "scrollbar.background": "bg:#1e1e1e",
    "scrollbar.button": "bg:#444444",
})


async def _handle_command(agent: Agent, raw: str) -> bool:
    """处理斜杠命令，返回 True 表示已处理。"""
    parts = raw.split(maxsplit=1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/help", "/h", "/?"):
        print("\n可用命令：")
        print("  /help, /h, /?        显示帮助")
        print("  /exit, /q, /quit     退出")
        print("  /reset, /clear       重置对话上下文")
        print("  /mode chat|agent     切换模式")
        print("  /skills              列出技能")
        print()
        return True

    if cmd in ("/exit", "/q", "/quit"):
        print("\nBye!")
        raise EOFError  # 退出 REPL 循环

    if cmd in ("/reset", "/clear"):
        agent.context = type(agent.context)()  # 重建上下文
        print("\n✓ 上下文已重置\n")
        return True

    if cmd == "/mode":
        if arg == "chat":
            print(f"\n✓ 已切换到 chat 模式\n")
        elif arg == "agent":
            print(f"\n✓ 已切换到 agent 模式\n")
        else:
            print(f"\n用法: /mode chat|agent\n")
        return True

    if cmd == "/skills":
        skills = agent.skill_loader.list_skills() if hasattr(agent.skill_loader, "list_skills") else []
        if skills:
            print("\n已加载技能：")
            for s in skills:
                print(f"  - {s}")
        else:
            print("\n(无已加载技能)\n")
        return True

    print(f"\n未知命令: {cmd}（输入 /help 查看帮助）\n")
    return False


async def run_repl(agent: Agent) -> None:
    session = PromptSession(
        completer=SlashCompleter(),
        message=HTML("<b><ansigreen>&gt;</ansigreen></b> "),
        style=REPL_STYLE,
    )

    print("输入消息 (Ctrl+D to exit, /help 查看命令)\n")

    while True:
        try:
            user_input = await session.prompt_async()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        stripped = user_input.strip()
        if not stripped:
            continue

        # ── 处理 `/` 命令 ──
        if stripped.startswith("/"):
            try:
                await _handle_command(agent, stripped)
            except EOFError:
                break
            continue

        print()
        await agent.run(stripped)
        print()
