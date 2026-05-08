"""会话管理 — 每个用户 × 每个角色维护独立对话历史。

支持持久化到本地 JSON 文件，重启后对话历史不丢失。
"""

import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# 数据文件路径
_DATA_DIR = Path.home() / ".nonebot2" / "data" / "dotcharacter"
_SESSIONS_FILE = _DATA_DIR / "sessions.json"


@dataclass
class ConversationSession:
    """单个用户对单个角色的对话会话。"""
    user_id: str
    character_slug: str
    messages: List[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)
    _manager: Optional["ConversationManager"] = field(default=None, repr=False)

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self.last_active_at = time.time()
        if self._manager:
            self._manager._save()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})
        self.last_active_at = time.time()
        if self._manager:
            self._manager._save()

    def trim(self, max_history: int) -> None:
        """保留最近 N 轮对话（每轮 = user + assistant）。"""
        if max_history <= 0:
            self.messages.clear()
            if self._manager:
                self._manager._save()
            return
        if len(self.messages) > max_history:
            self.messages = self.messages[-max_history:]
        if self._manager:
            self._manager._save()

    @property
    def is_empty(self) -> bool:
        return len(self.messages) == 0

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "character_slug": self.character_slug,
            "messages": self.messages,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
        }

    @classmethod
    def from_dict(cls, data: dict, manager: Optional["ConversationManager"] = None) -> "ConversationSession":
        return cls(
            user_id=data["user_id"],
            character_slug=data["character_slug"],
            messages=data.get("messages", []),
            created_at=data.get("created_at", time.time()),
            last_active_at=data.get("last_active_at", time.time()),
            _manager=manager,
        )


class ConversationManager:
    """管理所有用户的会话。

    内部使用 OrderedDict 做简单的 LRU 淘汰，
    支持持久化到本地 JSON 文件。
    """

    MAX_SESSIONS = 500  # 最多保留 500 个会话

    def __init__(self) -> None:
        self._sessions: OrderedDict[str, ConversationSession] = OrderedDict()
        self._active_character: Dict[str, str] = {}  # user_id → slug
        self._load()

    def _save(self) -> None:
        """将会话状态持久化到本地文件。"""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "sessions": {
                    key: session.to_dict()
                    for key, session in self._sessions.items()
                },
                "active_characters": dict(self._active_character),
            }
            _SESSIONS_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass  # 保存失败不影响运行

    def _load(self) -> None:
        """从本地文件恢复会话状态。"""
        if not _SESSIONS_FILE.exists():
            return
        try:
            raw = _SESSIONS_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
            sessions_data = data.get("sessions", {})
            for key, sess_data in sessions_data.items():
                session = ConversationSession.from_dict(sess_data, manager=self)
                self._sessions[key] = session
            self._active_character = data.get("active_characters", {})
        except Exception:
            pass  # 加载失败不影响运行

    def _make_key(self, user_id: str, slug: str) -> str:
        return f"{user_id}::{slug}"

    def get_session(self, user_id: str, slug: str) -> ConversationSession:
        """获取或创建会话。"""
        key = self._make_key(user_id, slug)
        if key not in self._sessions:
            if len(self._sessions) >= self.MAX_SESSIONS:
                # 淘汰最老的会话
                self._sessions.popitem(last=False)
            self._sessions[key] = ConversationSession(
                user_id=user_id,
                character_slug=slug,
                _manager=self,
            )
            self._save()
        else:
            # 移到末尾（最近使用）
            self._sessions.move_to_end(key)
        return self._sessions[key]

    def reset_session(self, user_id: str, slug: str) -> None:
        """重置某用户对某角色的对话。"""
        key = self._make_key(user_id, slug)
        self._sessions.pop(key, None)
        self._save()

    def set_active_character(self, user_id: str, slug: str) -> None:
        self._active_character[user_id] = slug
        self._save()

    def get_active_character(self, user_id: str) -> Optional[str]:
        return self._active_character.get(user_id)

    def clear_active_character(self, user_id: str) -> None:
        self._active_character.pop(user_id, None)
        self._save()

    def cleanup_stale(self, max_age_seconds: float = 3600.0) -> int:
        """清理超过 max_age_seconds 未活跃的会话。返回清理数量。"""
        now = time.time()
        stale_keys = [
            key
            for key, session in self._sessions.items()
            if now - session.last_active_at > max_age_seconds
        ]
        for key in stale_keys:
            self._sessions.pop(key, None)
        self._save()
        return len(stale_keys)


# 全局单例
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
