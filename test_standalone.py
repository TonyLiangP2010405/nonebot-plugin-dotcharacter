"""独立测试脚本 — 无需 NoneBot，直接测试 dot-skill 角色加载并与 LLM 对话。

用法：
  python test_standalone.py                         # 交互式对话
  python test_standalone.py --list                  # 列出角色
  python test_standalone.py --test 小小桃子呦        # 测试指定角色
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 模拟 NoneBot 环境变量加载
if not os.environ.get("DOTCHARACTER_API_KEY"):
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ[key.strip()] = val.strip()

import importlib

_base = str(Path(__file__).parent / "nonebot_plugin_dotcharacter")

spec = importlib.util.spec_from_file_location(
    "nonebot_plugin_dotcharacter",
    _base + "\\__init__.py",
    submodule_search_locations=[_base],
)
package = importlib.util.module_from_spec(spec)
sys.modules["nonebot_plugin_dotcharacter"] = package

for name in ["config", "character_loader", "conversation", "llm_client"]:
    mod_spec = importlib.util.spec_from_file_location(
        f"nonebot_plugin_dotcharacter.{name}",
        f"{_base}\\{name}.py",
    )
    mod = importlib.util.module_from_spec(mod_spec)
    sys.modules[f"nonebot_plugin_dotcharacter.{name}"] = mod
    mod_spec.loader.exec_module(mod)

DotCharacterConfig = sys.modules["nonebot_plugin_dotcharacter.config"].DotCharacterConfig
scan_characters = sys.modules["nonebot_plugin_dotcharacter.character_loader"].scan_characters
resolve_character = sys.modules["nonebot_plugin_dotcharacter.character_loader"].resolve_character
llm_mod = sys.modules["nonebot_plugin_dotcharacter.llm_client"]


def get_config() -> DotCharacterConfig:
    return DotCharacterConfig(
        dotcharacter_provider=os.environ.get("DOTCHARACTER_PROVIDER", "deepseek"),
        dotcharacter_api_base=os.environ.get("DOTCHARACTER_API_BASE", "https://api.openai.com/v1"),
        dotcharacter_api_key=os.environ.get("DOTCHARACTER_API_KEY", ""),
        dotcharacter_model=os.environ.get("DOTCHARACTER_MODEL", "deepseek-chat"),
        dotcharacter_skills_path=os.environ.get("DOTCHARACTER_SKILLS_PATH", ""),
        dotcharacter_temperature=float(os.environ.get("DOTCHARACTER_TEMPERATURE", "0.8")),
        dotcharacter_max_tokens=int(os.environ.get("DOTCHARACTER_MAX_TOKENS", "1024")),
        dotcharacter_timeout=int(os.environ.get("DOTCHARACTER_TIMEOUT", "60")),
        dotcharacter_max_history=int(os.environ.get("DOTCHARACTER_MAX_HISTORY", "20")),
    )


async def run_test(config: DotCharacterConfig, char_name: str):
    print("[SEARCH] 扫描角色目录...")
    roots = config.resolve_skills_paths()
    if not roots:
        print("[ERR] 未找到角色目录。")
        return

    print(f"[OK] 角色目录: {len(roots)} 个")
    for r in roots:
        print(f"     {r}")

    loop = asyncio.get_running_loop()
    characters = await loop.run_in_executor(None, scan_characters, roots)
    print(f"[BOX] 发现 {len(characters)} 个角色: {list(characters.keys())}")

    char = resolve_character(char_name, characters)
    if not char:
        print(f"[ERR] 找不到角色「{char_name}」")
        return

    print(f"\n[MASK] 角色: {char.display_name} ({char.family})")
    print(f"   Persona: {len(char.persona_prompt)} chars")
    print(f"   Work: {len(char.work_prompt)} chars")
    print(f"   System prompt: {len(char.combined_prompt)} chars")
    print(f"\n{'='*50}")
    print(f"系统提示词预览（前 500 字符）:")
    print(f"{'='*50}")
    print(char.combined_prompt[:500])
    print(f"{'='*50}")

    if not config.dotcharacter_api_key or config.dotcharacter_api_key.startswith("sk-your-"):
        print("\n[WARN] 未设置有效的 DOTCHARACTER_API_KEY，跳过 LLM 调用测试。")
        return

    print("\n[ROBOT] 发送测试消息...")
    chat_completion = llm_mod.chat_completion
    system_msg = llm_mod.system_msg
    user_msg = llm_mod.user_msg

    messages = [
        system_msg(char.combined_prompt),
        user_msg("测试用户", "你好呀，很高兴认识你！"),
    ]

    try:
        reply = await chat_completion(config, messages)
        print(f"\n{char.display_name} 的回复:\n{reply}")
    except Exception as e:
        print(f"\n[ERR] API 调用失败: {e}")


async def run_interactive(config: DotCharacterConfig):
    roots = config.resolve_skills_paths()
    if not roots:
        print("[ERR] 未找到角色目录。")
        return

    loop = asyncio.get_running_loop()
    characters = await loop.run_in_executor(None, scan_characters, roots)
    if not characters:
        print("[ERR] 未找到任何角色。")
        return

    print("[MASK] 可用角色：")
    for slug, c in sorted(characters.items()):
        print(f"  {slug} — {c.display_name}")

    name = input("\n输入角色名称或 slug: ").strip()
    char = resolve_character(name, characters)
    if not char:
        print(f"找不到角色「{name}」")
        return

    print(f"\n开始与 {char.display_name} 对话。输入 /exit 退出，/reset 重置。\n")

    chat_completion = llm_mod.chat_completion
    system_msg = llm_mod.system_msg
    user_msg = llm_mod.user_msg

    messages = [system_msg(char.combined_prompt)]

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[BYE] 再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/exit", "/quit"):
            print("[BYE] 再见！")
            break
        if user_input.lower() == "/reset":
            messages = [system_msg(char.combined_prompt)]
            print("[RESET] 对话已重置。")
            continue

        messages.append(user_msg("用户", user_input))

        try:
            reply = await chat_completion(config, messages)
            print(f"{char.display_name}: {reply}\n")
            messages.append({"role": "assistant", "content": reply})
        except Exception as e:
            print(f"[ERR] 错误: {e}\n")


def main():
    parser = argparse.ArgumentParser(description="dot-skill 角色扮演测试工具")
    parser.add_argument("--list", action="store_true", help="列出所有角色")
    parser.add_argument("--test", type=str, metavar="NAME", help="测试指定角色")
    args = parser.parse_args()

    config = get_config()

    if args.list:
        roots = config.resolve_skills_paths()
        if not roots:
            print("[ERR] 未找到角色目录。")
            return
        characters = scan_characters(roots)
        print(f"[BOX] {len(characters)} 个角色：")
        for slug, c in sorted(characters.items()):
            print(f"  [{c.family}] {slug}")
            print(f"    名称: {c.display_name}")
            print(f"    描述: {c.description}")
            print(f"    标签: {c.tags}")
            print()
        return

    if args.test:
        asyncio.run(run_test(config, args.test))
        return

    asyncio.run(run_interactive(config))


if __name__ == "__main__":
    main()
