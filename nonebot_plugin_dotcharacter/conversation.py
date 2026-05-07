"""会话管理 — 每个用户 × 每个角色维护独立对话历史。"""

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ConversationSession:
    """单个用户对单个角色的对话会话。"""
    user_id: str
    character_slug: str
    messages: List[dict] = field(default_factory=list)  # [{"role":"user"|"assistant","content":"..."}]
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self.last_active_at = time.time()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})
        self.last_active_at = time.time()

    def trim(self, max_history: int) -> None:
        """保留最近 N 轮对话（每轮 = user + assistant）。"""
        if max_history <= 0:
            self.messages.clear()
            return
        # max_history 指的是消息数，保留最后 N 条
        if len(self.messages) > max_history:
            self.messages = self.messages[-max_history:]

    @property
    def is_empty(self) -> bool:
        return len(self.messages) == 0


class ConversationManager:
    """管理所有用户的会话。

    内部使用 OrderedDict 做简单的 LRU 淘汰，
    避免长时间运行时内存无限增长。
    """

    MAX_SESSIONS = 500  # 最多保留 500 个会话

    def __init__(self) -> None:
        self._sessions: OrderedDict[str, ConversationSession] = OrderedDict()
        self._active_character: Dict[str, str] = {}  # user_id → slug

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
            )
        else:
            # 移到末尾（最近使用）
            self._sessions.move_to_end(key)
        return self._sessions[key]

    def reset_session(self, user_id: str, slug: str) -> None:
        """重置某用户对某角色的对话。"""
        key = self._make_key(user_id, slug)
        self._sessions.pop(key, None)

    def set_active_character(self, user_id: str, slug: str) -> None:
        self._active_character[user_id] = slug

    def get_active_character(self, user_id: str) -> Optional[str]:
        return self._active_character.get(user_id)

    def clear_active_character(self, user_id: str) -> None:
        self._active_character.pop(user_id, None)

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
        return len(stale_keys)


# 全局单例
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
