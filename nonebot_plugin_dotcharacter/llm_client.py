"""LLM 客户端 — 调用 OpenAI 兼容 API 进行角色对话。

支持所有 OpenAI Chat Completions 兼容的 API：
OpenAI / DeepSeek / Kimi / Qwen / Zhipu / SiliconFlow / Groq / Ollama / 自定义
"""

from typing import List, Optional

import httpx

from .config import DotCharacterConfig


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


def system_msg(content: str) -> dict:
    return _msg("system", content)


def user_msg(name: str, content: str) -> dict:
    return _msg("user", f"{name}: {content}")


def assistant_msg(content: str) -> dict:
    return _msg("assistant", content)


async def chat_completion(
    config: DotCharacterConfig,
    messages: List[dict],
    max_tokens: Optional[int] = None,
) -> str:
    """发送聊天请求到 LLM，返回助手回复文本。

    自动根据 Provider 预设或自定义 api_base 构造请求 URL。
    兼容所有 OpenAI Chat Completions 格式的 API。
    """
    api_key = config.dotcharacter_api_key
    if not api_key or api_key.startswith("sk-your-"):
        raise ValueError(
            "未配置有效的 DOTCHARACTER_API_KEY。"
            "请在 .env 中设置真实的 API Key。"
        )

    base_url = config.get_api_base().rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.dotcharacter_model,
        "messages": messages,
        "temperature": config.dotcharacter_temperature,
        "max_tokens": max_tokens or config.dotcharacter_max_tokens,
    }

    async with httpx.AsyncClient(timeout=config.dotcharacter_timeout) as client:
        response = await client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            err_detail = response.text[:500]
            raise RuntimeError(
                f"LLM API 返回错误 (HTTP {response.status_code}): {err_detail}"
            )

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"LLM API 返回空 choices: {data}")

        content = choices[0].get("message", {}).get("content", "")
        return content.strip()


async def test_api_connection(config: DotCharacterConfig) -> bool:
    """快速测试 API 连接是否正常。"""
    try:
        result = await chat_completion(
            config,
            messages=[
                system_msg("回复 OK，只输出这两个字母。"),
                user_msg("test", "ping"),
            ],
            max_tokens=10,
        )
        return "OK" in result.upper()
    except Exception:
        return False
