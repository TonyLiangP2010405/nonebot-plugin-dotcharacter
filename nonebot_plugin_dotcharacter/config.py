"""配置模型 — 通过 NoneBot 的 Config 或 .env 文件读取。"""

from pathlib import Path
from typing import Dict, List
from nonebot import get_plugin_config
from pydantic import BaseModel, Field, field_validator


# ── 大模型 Provider 预设 ──
PROVIDER_PRESETS: Dict[str, dict] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o4-mini"],
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4-flash", "glm-4-air"],
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "models": ["Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"],
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3", "qwen2.5", "mistral"],
    },
    "custom": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini"],
    },
}


class DotCharacterConfig(BaseModel):
    """dot-skill 角色扮演插件配置。"""

    # ── LLM Provider ──
    dotcharacter_provider: str = Field(
        default="custom",
        description="大模型 Provider 预设：openai / deepseek / kimi / qwen / zhipu / siliconflow / groq / ollama / custom",
    )
    dotcharacter_api_base: str = Field(
        default="https://api.openai.com/v1",
        description="API 地址（provider=custom 时使用）",
    )
    dotcharacter_api_key: str = Field(
        default="",
        description="API Key",
    )
    dotcharacter_model: str = Field(
        default="gpt-4o-mini",
        description="模型名称",
    )
    dotcharacter_temperature: float = Field(
        default=0.8, ge=0.0, le=2.0,
    )
    dotcharacter_max_tokens: int = Field(
        default=1024, ge=1, le=32768,
    )
    dotcharacter_timeout: int = Field(
        default=60, ge=5,
    )

    # ── 角色目录（逗号分隔多个路径）──
    dotcharacter_skills_path: str = Field(
        default="",
        description="dot-skill / colleague-skill 角色目录，逗号分隔",
    )

    # ── 对话 ──
    dotcharacter_max_history: int = Field(
        default=20, ge=0, le=100,
    )

    # ── 权限 ──
    dotcharacter_admin_qq: str = Field(default="")
    dotcharacter_allowed_groups: str = Field(default="")

    def get_admin_qqs(self) -> List[str]:
        return [q.strip() for q in str(self.dotcharacter_admin_qq).split(",") if q.strip()]

    def get_allowed_groups(self) -> List[str]:
        return [g.strip() for g in str(self.dotcharacter_allowed_groups).split(",") if g.strip()]

    @field_validator("dotcharacter_admin_qq", "dotcharacter_allowed_groups", mode="before")
    @classmethod
    def _coerce_to_str(cls, v):
        return str(v) if v is not None else ""

    def get_api_base(self) -> str:
        if self.dotcharacter_provider and self.dotcharacter_provider != "custom":
            preset = PROVIDER_PRESETS.get(self.dotcharacter_provider)
            if preset:
                return preset["base_url"]
        return self.dotcharacter_api_base

    def get_available_models(self) -> List[str]:
        if self.dotcharacter_provider and self.dotcharacter_provider != "custom":
            preset = PROVIDER_PRESETS.get(self.dotcharacter_provider)
            if preset:
                return preset["models"]
        return [self.dotcharacter_model]

    def resolve_skills_paths(self) -> List[Path]:
        """解析所有角色目录，支持逗号分隔 + 自动发现。

        检测顺序：
        1. DOTCHARACTER_SKILLS_PATH 指定的路径（逗号分隔）
        2. Claude Code / Hermes / OpenClaw 默认位置
        3. colleague-skill 仓库常见克隆位置
        """
        candidates: List[Path] = []

        if self.dotcharacter_skills_path:
            for p in self.dotcharacter_skills_path.split(","):
                p = p.strip()
                if p:
                    candidates.append(Path(p))

        home = Path.home()
        candidates.append(home / ".claude" / "skills" / "dot-skill" / "skills")
        candidates.append(home / ".hermes" / "skills" / "dot-skill" / "skills")
        candidates.append(home / ".openclaw" / "workspace" / "skills" / "dot-skill" / "skills")
        candidates.append(home / "colleague-skill" / "skills")
        candidates.append(home / "dot-skill" / "skills")
        candidates.append(home / "Documents" / "colleague-skill" / "skills")
        candidates.append(home / "code" / "colleague-skill" / "skills")
        candidates.append(home / "projects" / "colleague-skill" / "skills")

        seen: set = set()
        result: List[Path] = []
        for p in candidates:
            try:
                resolved = p.resolve()
            except OSError:
                continue
            key = str(resolved)
            if resolved.exists() and resolved.is_dir() and key not in seen:
                seen.add(key)
                result.append(resolved)
        return result


def get_config() -> DotCharacterConfig:
    return get_plugin_config(DotCharacterConfig)
