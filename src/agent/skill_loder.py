import re
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path

class SkillLoader:
    def __init__(self, skill_dir: str | Path = "skills"):
        self._dir = Path(skill_dir)
        self._skills: dict[str, Skill] = {}
        # self._load_skills()
        
    def _load_all(self) -> None:
        if not self._dir.exists():
            return
        for skill_file in self._dir.rglob("SKILL.md"):
            skill = self._parse(skill_file)
    
    def _parse(self, path: Path) -> Skill | None:
        text = path.read_text(encoding="utf-8")
        """re.DOTALL: make . match newlines"""
        match = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
        meta: dict[str, str] = {}
        body = text
        
        if match:
            for line in match.group(1).strip().splitlines():
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
            body = match.group(2).strip()
            
        breakpoint()
        name = meta.get("name", path.stem) # path.parent.name
        description = meta.get("description", "")
        
        if not name or len(name) > 64:
            return None
        if not description:
            return None
        
        return Skill(name=name, description=description, body=body, path=path)
        