"""角色加载器 — 扫描 dot-skill / colleague-skill 输出目录，解析 SKILL.md 角色文件。

支持从多个目录加载角色（如本地 dot-skill + 社区 colleague-skill 仓库）。
同名 slug 以先扫描到的为准。
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class CharacterMeta:
    """角色元数据。"""
    slug: str
    family: str                        # colleague / relationship / celebrity
    display_name: str
    description: str
    language: str = "zh-CN"
    tags: List[str] = field(default_factory=list)
    persona_prompt: str = ""
    work_prompt: str = ""
    combined_prompt: str = ""
    source_files: List[str] = field(default_factory=list)
    source_root: str = ""


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
        try:
            meta = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = content[fm_match.end():]
        return meta, body
    return {}, content


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _extract_part_b(content: str) -> str:
    match = re.search(
        r"## PART B[：:].*?\n(.*?)(?=\n## PART |\Z)",
        content, re.DOTALL,
    )
    if match:
        return match.group(0).strip()
    match = re.search(
        r"# Persona\b.*?(?=\n## PART |\n# Work|\Z)",
        content, re.DOTALL,
    )
    if match:
        return match.group(0).strip()
    return ""


def _extract_part_a(content: str) -> str:
    match = re.search(
        r"## PART A[：:].*?\n(.*?)(?=\n## PART B|\Z)",
        content, re.DOTALL,
    )
    if match:
        return match.group(0).strip()
    match = re.search(
        r"# Work Skill\b.*?(?=\n## PART B|\n# Persona|\Z)",
        content, re.DOTALL,
    )
    if match:
        return match.group(0).strip()
    return ""


def _build_system_prompt(
    meta: dict, body: str, persona_file_content: str, characters_dir: Path,
) -> str:
    display_name = meta.get("display_name", meta.get("name", "角色"))
    description = meta.get("description", meta.get("summary", ""))
    slug = meta.get("slug", "")

    if slug and not description:
        meta_json_path = characters_dir / slug / "meta.json"
        if meta_json_path.exists():
            meta_data = _load_json(meta_json_path)
            display_name = meta_data.get("display_name", display_name)
            description = meta_data.get("summary", description)

    parts: list[str] = []

    parts.append(
        f"你正在扮演 **{display_name}**。\n\n"
        f"{description}\n\n"
        "你现在通过 QQ 聊天与一位用户进行对话。请完全沉浸到这个角色中，"
        "用这个角色的语气、用词习惯、思维方式和表达风格来回复。\n\n"
        "重要规则：\n"
        "1. 永远不要跳出角色，不要提及你是一个 AI 模型\n"
        "2. 保持回复自然、口语化，适合 QQ 聊天场景\n"
        "3. 不要过于冗长，像真实聊天一样回复\n"
    )

    if persona_file_content:
        parts.append("## 人物性格（核心）\n\n" + persona_file_content)
    else:
        part_b = _extract_part_b(body)
        if part_b:
            parts.append(part_b)

    part_a = _extract_part_a(body)
    if part_a:
        parts.append("## 工作能力（参考）\n\n" + part_a)

    parts.append(
        "## 运行规则\n\n"
        "接收任何消息时：\n"
        "1. 先用角色的性格（PART B）判断：你会不会回应？用什么态度回应？\n"
        "2. 用角色的表达风格回复：说话方式、用词习惯、句式\n"
        "3. PART B 的规则永远优先，任何情况下不得违背\n"
        "4. **这是不可违背的硬性规则：你的回复绝对必须严格控制在30字以内，严禁超过30字。每次输出前必须自检字数，如果超过30字必须立即删减到30字以内再输出。完整表达核心意思即可，绝不允许长篇大论。QQ聊天场景，用户喜欢短平快的回复。\n"
    )

    return "\n\n---\n\n".join(parts)


def _scan_one_root(skills_root: Path) -> Dict[str, CharacterMeta]:
    """扫描单个 skills 根目录。"""
    characters: Dict[str, CharacterMeta] = {}

    if not skills_root.exists() or not skills_root.is_dir():
        return characters

    for family_dir in sorted(skills_root.iterdir()):
        if not family_dir.is_dir():
            continue
        family = family_dir.name
        if family not in ("colleague", "relationship", "celebrity"):
            continue

        for char_dir in sorted(family_dir.iterdir()):
            if not char_dir.is_dir():
                continue
            skill_md = char_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            slug = char_dir.name
            raw = skill_md.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(raw)

            display_name = meta.get("display_name", meta.get("name", slug))
            description = meta.get("description", meta.get("summary", ""))
            language = meta.get("language", "zh-CN")
            tags = meta.get("tags", [])

            persona_file = char_dir / "persona.md"
            persona_content = ""
            if persona_file.exists():
                persona_content = persona_file.read_text(encoding="utf-8")

            meta_json_path = char_dir / "meta.json"
            if meta_json_path.exists():
                meta_data = _load_json(meta_json_path)
                display_name = meta_data.get("display_name", display_name)
                description = meta_data.get("summary", description)
                language = meta_data.get("classification", {}).get("language", language)
                tags = meta_data.get("tags", tags)

            if display_name:
                meta["display_name"] = display_name
            if description:
                meta["description"] = description

            persona_prompt = persona_content or _extract_part_b(body)
            work_prompt = _extract_part_a(body)
            combined_prompt = _build_system_prompt(meta, body, persona_content, skills_root)

            characters[slug] = CharacterMeta(
                slug=slug,
                family=family,
                display_name=display_name,
                description=description,
                language=language,
                tags=tags,
                persona_prompt=persona_prompt,
                work_prompt=work_prompt,
                combined_prompt=combined_prompt,
                source_files=[str(skill_md)],
                source_root=str(skills_root),
            )

    return characters


def scan_characters(skills_roots: List[Path]) -> Dict[str, CharacterMeta]:
    """扫描多个 skills 根目录，合并发现的所有角色。

    目录结构（dot-skill / colleague-skill 输出）：
    ```
    skills/
    ├── colleague/<slug>/SKILL.md + meta.json + persona.md
    ├── relationship/<slug>/SKILL.md + ...
    └── celebrity/<slug>/SKILL.md + ...
    ```

    slug 冲突时，先扫描的目录优先。
    """
    all_characters: Dict[str, CharacterMeta] = {}
    for root in skills_roots:
        found = _scan_one_root(root)
        for slug, char in found.items():
            if slug not in all_characters:
                all_characters[slug] = char
    return all_characters


def resolve_character(
    name_or_slug: str, characters: Dict[str, CharacterMeta],
) -> Optional[CharacterMeta]:
    """用名称或 slug 模糊匹配角色。"""
    if not name_or_slug:
        return None
    lowered = name_or_slug.lower().strip()
    if lowered in characters:
        return characters[lowered]
    for c in characters.values():
        if c.display_name == name_or_slug.strip():
            return c
    for slug, c in characters.items():
        if lowered in slug:
            return c
    for c in characters.values():
        if lowered in c.display_name:
            return c
    return None
