"""限流模块 — 分群分人管理对话频率。

每个 scope（群/私聊）可独立设置 10 分钟窗口内的最大请求次数。
每个用户在该 scope 内独立计数。
"""

import time
from typing import Dict, Tuple

# 限流计数器: {(scope_id, user_id): {"count": int, "window_start": float}}
_rate_limits: Dict[Tuple[str, str], dict] = {}

# 各 scope 的限流阈值: {scope_id: max_requests_per_window}
# 0 或 None 表示不限制
_scope_limits: Dict[str, int] = {}

WINDOW_SECONDS = 600  # 10 分钟


def check_rate_limit(scope_id: str, user_id: str) -> Tuple[bool, str]:
    """检查是否允许本次请求。

    返回: (是否允许, 提示消息或 None)
    """
    limit = _scope_limits.get(scope_id, 0)
    if limit <= 0:
        return True, None

    key = (scope_id, user_id)
    now = time.time()
    state = _rate_limits.get(key)

    if state is None or now - state["window_start"] > WINDOW_SECONDS:
        # 新窗口
        _rate_limits[key] = {"count": 1, "window_start": now}
        return True, None

    if state["count"] < limit:
        state["count"] += 1
        return True, None

    remaining = int(WINDOW_SECONDS - (now - state["window_start"]))
    mins = remaining // 60
    secs = remaining % 60
    time_str = f"{mins}分{secs}秒" if mins > 0 else f"{secs}秒"
    return False, (
        f"⏳ 对话太快了，请 {time_str} 后再试～\n"
        f"（本群限流：{limit} 次/10分钟，每人独立计数）"
    )


def set_limit(scope_id: str, limit: int) -> None:
    """设置某 scope 的限流阈值。limit <= 0 表示关闭限流。"""
    if limit <= 0:
        _scope_limits.pop(scope_id, None)
    else:
        _scope_limits[scope_id] = limit


def get_limit(scope_id: str) -> int:
    """获取某 scope 的限流阈值，0 表示无限制。"""
    return _scope_limits.get(scope_id, 0)


def get_status(scope_id: str, user_id: str) -> dict:
    """获取某用户在某 scope 的限流状态。"""
    key = (scope_id, user_id)
    state = _rate_limits.get(key)
    limit = _scope_limits.get(scope_id, 0)
    now = time.time()

    if state and now - state["window_start"] <= WINDOW_SECONDS:
        return {
            "limit": limit,
            "count": state["count"],
            "remaining": max(0, limit - state["count"]),
            "window_reset": int(WINDOW_SECONDS - (now - state["window_start"])),
        }
    return {
        "limit": limit,
        "count": 0,
        "remaining": limit,
        "window_reset": WINDOW_SECONDS,
    }
