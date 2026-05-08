"""NoneBot 插件：dot-skill 角色扮演

加载 dot-skill / colleague-skill 蒸馏的角色 Persona，通过 QQ Bot 进行 AI 角色扮演对话。

权限模型：
  - 命令（!角色列表 / !角色切换 等）：仅管理员可用
  - 角色扮演对话：所有用户可用
  - 群聊 @机器人 才触发对话（命令不需要 @）

支持 OpenAI / DeepSeek / Kimi / Qwen / Zhipu / SiliconFlow / Groq / Ollama / 自定义
等所有 OpenAI Chat Completions 兼容的大模型 API。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict

from nonebot import on_command, on_message, get_driver, logger
from nonebot.adapters import Event, Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.permission import Permission
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

# 本地存储实例（NoneBot 启动后才可用）
_store = None


def _get_store():
    """懒加载 localstore，仅在 NoneBot 运行时导入。"""
    global _store
    if _store is None:
        try:
            import nonebot_plugin_localstore as s
            _store = s
        except Exception:
            pass
    return _store

from .config import get_config, PROVIDER_PRESETS, DotCharacterConfig
from .character_loader import (
    CharacterMeta,
    scan_characters,
    resolve_character,
)
from .conversation import get_conversation_manager
from .llm_client import chat_completion, system_msg, user_msg


__plugin_meta__ = PluginMetadata(
    name="dot-skill 角色扮演",
    description="加载 dot-skill / colleague-skill 蒸馏的角色 Persona，通过 QQ 进行 AI 角色扮演对话。"
    "支持群聊 @机器人、多模型切换（DeepSeek/OpenAI/Kimi 等）、管理员权限控制。",
    usage=(
        "命令（仅管理员）：\n"
        "  !角色列表 — 列出所有角色\n"
        "  !角色切换 <名称> — 切换到指定角色，开始对话\n"
        "  !角色退出 — 退出当前角色\n"
        "  !重置对话 — 清空对话历史\n"
        "  !角色信息 [名称] — 查看角色详情\n"
        "  !角色路径 — 查看角色目录\n"
        "  !角色刷新 — 重新扫描角色目录\n"
        "  !角色导入 add <路径> — 添加角色目录\n"
        "  !模型切换 provider/model <名称> — 切换 LLM\n"
        "\n"
        "切换到角色后，直接发消息即可对话。群聊中需 @机器人。"
    ),
    type="application",
    homepage="https://github.com/TonyLiangP2010405/nonebot-plugin-dotcharacter",
    config=DotCharacterConfig,
    supported_adapters={"~onebot.v11"},
    extra={
        "author": "tghrt",
        "version": "2.0.5",
    },
)


# ═══════════════════════════════════════════════
# 全局状态
# ═══════════════════════════════════════════════

_characters: Dict[str, CharacterMeta] = {}
_initialized: bool = False
_init_lock = asyncio.Lock()


async def _reload_characters() -> int:
    """重新扫描所有角色目录，返回发现的角色数。"""
    global _characters
    cfg = get_config()
    roots = cfg.resolve_skills_paths()
    if not roots:
        _characters = {}
        return 0
    logger.info(f"[dotcharacter] 重新扫描角色目录 ({len(roots)} 个路径)...")
    loop = asyncio.get_running_loop()
    _characters = await loop.run_in_executor(None, scan_characters, roots)
    logger.info(
        f"[dotcharacter] 发现 {len(_characters)} 个角色: {list(_characters.keys())}"
    )
    return len(_characters)


async def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    async with _init_lock:
        if _initialized:
            return
        try:
            count = await _reload_characters()
            if count == 0:
                logger.warning(
                    "[dotcharacter] 未找到任何角色目录。"
                    "请设置 DOTCHARACTER_SKILLS_PATH 指向 skills 目录。"
                )
        except Exception as e:
            logger.error(f"[dotcharacter] 初始化失败: {e}")
        finally:
            _initialized = True


# ═══════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════

def _get_raw_qq(event: Event) -> str:
    uid = event.get_user_id()
    return uid.replace("user_", "")


def _get_user_name(event: Event) -> str:
    try:
        sender = event.get_sender_name()
        if sender:
            return sender
    except Exception:
        pass
    try:
        card = event.sender.card if hasattr(event.sender, "card") else None
        if card:
            return card
    except Exception:
        pass
    return "用户"


def _is_group(event: Event) -> bool:
    return getattr(event, "message_type", "") == "group"


def _get_group_id(event: Event) -> str:
    return str(getattr(event, "group_id", ""))


def _is_at_bot(event: Event) -> bool:
    if hasattr(event, "is_tome") and callable(event.is_tome):
        return event.is_tome()
    try:
        for seg in event.get_message():
            if seg.type == "at" and seg.data.get("qq") == str(event.self_id):
                return True
    except Exception:
        pass
    return False


def _is_admin(event: Event) -> bool:
    cfg = get_config()
    admins = cfg.get_admin_qqs()
    if not admins:
        return False
    return _get_raw_qq(event) in admins


def _is_group_allowed(event: Event) -> bool:
    if not _is_group(event):
        return True
    cfg = get_config()
    allowed = cfg.get_allowed_groups()
    if not allowed:
        return True
    return _get_group_id(event) in allowed


def _scope_id(event: Event) -> str:
    if _is_group(event):
        return f"group:{_get_group_id(event)}"
    return event.get_user_id()


async def _combined_perm(event: Event) -> bool:
    return _is_admin(event) and _is_group_allowed(event)


ADMIN_AND_GROUP = Permission(_combined_perm)


# ═══════════════════════════════════════════════
# 命令：角色列表
# ═══════════════════════════════════════════════

cmd_list = on_command(
    "角色列表", aliases={"角色 list", "characters", "角色"},
    priority=5, block=True, permission=ADMIN_AND_GROUP,
)


@cmd_list.handle()
async def handle_list(matcher: Matcher, event: Event):
    await _ensure_initialized()
    if not _characters:
        await matcher.finish(
            "📭 还没有加载任何角色。\n\n"
            "请先用 dot-skill 或 colleague-skill 蒸馏一个角色。\n"
            "设置 DOTCHARACTER_SKILLS_PATH 指向 skills 目录。"
        )

    cfg = get_config()
    provider = cfg.dotcharacter_provider
    model = cfg.dotcharacter_model
    roots = cfg.resolve_skills_paths()

    lines = [f"🎭 **可用角色列表** （LLM：{provider}/{model}，{len(roots)} 个目录）\n"]
    for i, (slug, c) in enumerate(sorted(_characters.items()), 1):
        family_emoji = {
            "colleague": "👔", "relationship": "💞", "celebrity": "🌟"
        }.get(c.family, "❓")
        lines.append(f"{i}. {family_emoji} **{c.display_name}**")
        lines.append(f"   `{slug}` — {c.description[:60]}")
        lines.append("")

    lines.append("使用 **!角色切换 <名称>** 开始对话。")
    await matcher.finish("\n".join(lines))


# ═══════════════════════════════════════════════
# 命令：角色切换
# ═══════════════════════════════════════════════

cmd_switch = on_command(
    "角色切换", aliases={"角色 switch", "switch_char", "chat"},
    priority=5, block=True, permission=ADMIN_AND_GROUP,
)


@cmd_switch.handle()
async def handle_switch(matcher: Matcher, event: Event, args: Message = CommandArg()):
    await _ensure_initialized()
    name = args.extract_plain_text().strip()
    if not name:
        await matcher.finish(
            "请指定角色名称或 slug。\n"
            "示例：!角色切换 小小桃子呦\n"
            "用 **!角色列表** 查看所有可用角色。"
        )

    char = resolve_character(name, _characters)
    if not char:
        await matcher.finish(
            f"❌ 找不到角色「{name}」。\n用 **!角色列表** 查看可用角色。"
        )

    sid = _scope_id(event)
    mgr = get_conversation_manager()
    mgr.set_active_character(sid, char.slug)

    session = mgr.get_session(sid, char.slug)
    history_hint = ""
    if not session.is_empty:
        history_hint = "\n📝 有之前的对话记录。用 **!重置对话** 清除。"

    family_emoji = {
        "colleague": "👔", "relationship": "💞", "celebrity": "🌟"
    }.get(char.family, "🎭")
    hint = "\n💡 群聊中请 **@机器人** 发送对话哦～" if _is_group(event) else ""

    await matcher.finish(
        f"{family_emoji} 已切换到 **{char.display_name}**\n"
        f"「{char.description}」\n\n"
        f"现在直接发消息就可以和 {char.display_name} 对话了～"
        f"{history_hint}{hint}\n\n"
        f"命令：!角色退出 | !重置对话 | !角色列表"
    )


# ═══════════════════════════════════════════════
# 命令：角色退出 / 重置 / 信息
# ═══════════════════════════════════════════════

cmd_exit = on_command(
    "角色退出", aliases={"角色 exit", "exit_char"},
    priority=5, block=True, permission=ADMIN_AND_GROUP,
)


@cmd_exit.handle()
async def handle_exit(matcher: Matcher, event: Event):
    sid = _scope_id(event)
    mgr = get_conversation_manager()
    active = mgr.get_active_character(sid)
    if active:
        char = _characters.get(active)
        name = char.display_name if char else active
        mgr.clear_active_character(sid)
        await matcher.finish(f"👋 已退出与 **{name}** 的对话。")
    else:
        await matcher.finish("你当前没有在对话中。")


cmd_reset = on_command(
    "重置对话", aliases={"重置", "reset"},
    priority=5, block=True, permission=ADMIN_AND_GROUP,
)


@cmd_reset.handle()
async def handle_reset(matcher: Matcher, event: Event):
    sid = _scope_id(event)
    mgr = get_conversation_manager()
    active = mgr.get_active_character(sid)
    if active:
        mgr.reset_session(sid, active)
        char = _characters.get(active)
        name = char.display_name if char else active
        await matcher.finish(f"🔄 已重置与 **{name}** 的对话记录。")
    else:
        await matcher.finish("你当前没有在对话中。用 **!角色切换 <名称>** 开始。")


cmd_info = on_command(
    "角色信息", aliases={"角色 info", "char_info"},
    priority=5, block=True, permission=ADMIN_AND_GROUP,
)


@cmd_info.handle()
async def handle_info(matcher: Matcher, event: Event, args: Message = CommandArg()):
    await _ensure_initialized()
    name = args.extract_plain_text().strip()
    sid = _scope_id(event)
    mgr = get_conversation_manager()

    if not name:
        active = mgr.get_active_character(sid)
        if not active:
            await matcher.finish(
                "你当前没有在对话中。\n用 **!角色信息 <名称>** 查看指定角色的信息。"
            )
        name = active

    char = resolve_character(name, _characters)
    if not char:
        await matcher.finish(f"❌ 找不到角色「{name}」。")

    session = mgr.get_session(sid, char.slug)
    history_count = len(session.messages)

    info = (
        f"🎭 **{char.display_name}**\n"
        f"├ 类型：{char.family}\n"
        f"├ Slug：`{char.slug}`\n"
        f"├ 语言：{char.language}\n"
        f"├ 标签：{', '.join(char.tags) if char.tags else '无'}\n"
        f"├ 描述：{char.description}\n"
        f"├ 对话历史：{history_count} 条\n"
        f"├ 来源：{char.source_root}\n"
        f"└ 文件：{char.source_files[0] if char.source_files else '未知'}"
    )
    await matcher.finish(info)


# ═══════════════════════════════════════════════
# 命令：角色路径
# ═══════════════════════════════════════════════

cmd_paths = on_command(
    "角色路径", aliases={"路径", "paths"},
    priority=5, block=True, permission=ADMIN_AND_GROUP,
)


@cmd_paths.handle()
async def handle_paths(matcher: Matcher, event: Event):
    cfg = get_config()
    roots = cfg.resolve_skills_paths()
    count = len(_characters)

    lines = [f"📂 共扫描 {len(roots)} 个目录，加载 {count} 个角色：\n"]
    for i, r in enumerate(roots, 1):
        chars_in_root = [
            c.display_name for c in _characters.values()
            if c.source_root == str(r)
        ]
        lines.append(f"{i}. `{r}`")
        if chars_in_root:
            for name in chars_in_root:
                lines.append(f"   ├ 🎭 {name}")
        else:
            lines.append("   └ (无角色)")
        lines.append("")

    lines.append(
        "💡 **如何添加角色**：\n"
        "1. 把蒸馏好的角色文件夹放到任意目录\n"
        "2. 目录结构：`skills/colleague/xxx/SKILL.md` 等\n"
        "3. 在 .env 设置 DOTCHARACTER_SKILLS_PATH=你的路径\n"
        "4. 发 !角色刷新 立即加载"
    )
    await matcher.finish("\n".join(lines))


# ═══════════════════════════════════════════════
# 命令：角色刷新
# ═══════════════════════════════════════════════

cmd_reload = on_command(
    "角色刷新", aliases={"刷新角色", "reload"},
    priority=5, block=True, permission=ADMIN_AND_GROUP,
)


@cmd_reload.handle()
async def handle_reload(matcher: Matcher, event: Event):
    await matcher.send("🔄 正在重新扫描角色目录...")
    count = await _reload_characters()
    if count == 0:
        await matcher.finish("📭 未发现任何角色。请检查 DOTCHARACTER_SKILLS_PATH 配置。")
    names = [c.display_name for c in _characters.values()]
    await matcher.finish(
        f"✅ 已刷新！共发现 **{count}** 个角色：\n"
        + "\n".join(f"  • {n}" for n in names)
    )


# ═══════════════════════════════════════════════
# 命令：角色导入
# ═══════════════════════════════════════════════

cmd_import = on_command(
    "角色导入", aliases={"导入角色", "import"},
    priority=5, block=True, permission=ADMIN_AND_GROUP,
)


@cmd_import.handle()
async def handle_import(matcher: Matcher, event: Event, args: Message = CommandArg()):
    """添加角色目录路径。用法：!角色导入 add <路径>"""
    arg_text = args.extract_plain_text().strip()

    if not arg_text:
        cfg = get_config()
        roots = cfg.resolve_skills_paths()
        await matcher.finish(
            f"📂 **角色导入**\n\n"
            f"当前扫描 {len(roots)} 个目录，{len(_characters)} 个角色。\n\n"
            f"添加新目录：`!角色导入 add <路径>`\n"
            f"查看详情：`!角色路径`\n\n"
            f"💡 把蒸馏好的角色文件传到任意目录，\n"
            f"   然后 add 进来就行，不需要装 dot-skill。"
        )

    parts = arg_text.split(maxsplit=1)
    action = parts[0].lower()
    value = parts[1] if len(parts) > 1 else ""

    if action == "add":
        if not value:
            await matcher.finish(
                "❌ 请提供目录路径。\n示例：!角色导入 add /data/chars/skills"
            )

        p = Path(value)
        if not p.exists() or not p.is_dir():
            await matcher.finish(f"❌ 目录不存在：{p}")

        cfg = get_config()
        existing = cfg.dotcharacter_skills_path
        new_path = str(p)
        if new_path in existing:
            await matcher.finish("⚠️ 路径已在配置中。用 !角色刷新 重新扫描。")

        cfg.dotcharacter_skills_path = (
            f"{existing},{new_path}" if existing else new_path
        )

        await matcher.send(f"🔄 扫描 {new_path} ...")
        count = await _reload_characters()
        names = [c.display_name for c in _characters.values()]
        await matcher.finish(
            f"✅ 已添加！共 {count} 个角色：\n"
            + "\n".join(f"  • {n}" for n in names)
            + f"\n\n💡 永久生效：在 .env 中设置\n"
            + f"  DOTCHARACTER_SKILLS_PATH={cfg.dotcharacter_skills_path}"
        )
    else:
        await matcher.finish(
            f"❌ 未知操作「{action}」。\n用法：`!角色导入 add <路径>`"
        )


# ═══════════════════════════════════════════════
# 命令：模型切换
# ═══════════════════════════════════════════════

cmd_model = on_command(
    "模型切换", aliases={"模型", "model", "切换模型"},
    priority=5, block=True, permission=ADMIN_AND_GROUP,
)


@cmd_model.handle()
async def handle_model(matcher: Matcher, event: Event, args: Message = CommandArg()):
    cfg = get_config()
    arg_text = args.extract_plain_text().strip()

    if not arg_text:
        provider = cfg.dotcharacter_provider
        models = cfg.get_available_models()
        lines = [
            f"⚙️ **当前 LLM 配置**",
            f"├ Provider：`{provider}`",
            f"├ Base URL：`{cfg.get_api_base()}`",
            f"├ Model：`{cfg.dotcharacter_model}`",
            f"└ 可用模型：{', '.join(f'`{m}`' for m in models)}",
            "",
            "切换：`!模型切换 provider <名称>` / `!模型切换 model <名称>`",
        ]
        await matcher.finish("\n".join(lines))

    parts = arg_text.split(maxsplit=1)
    if len(parts) < 2:
        await matcher.finish(
            "用法：\n"
            "  !模型切换 provider deepseek\n"
            "  !模型切换 model deepseek-chat\n"
            f"  可用 Provider：{', '.join(PROVIDER_PRESETS.keys())}"
        )

    target, value = parts[0].lower(), parts[1].strip()

    if target == "provider":
        if value not in PROVIDER_PRESETS:
            await matcher.finish(
                f"❌ 未知 Provider「{value}」。\n"
                f"可用：{', '.join(PROVIDER_PRESETS.keys())}"
            )
        cfg.dotcharacter_provider = value
        preset = PROVIDER_PRESETS[value]
        await matcher.finish(
            f"✅ 已切换到 Provider **{value}**\n"
            f"   Base URL：`{preset['base_url']}`\n"
            f"   可用模型：{', '.join(f'`{m}`' for m in preset['models'])}\n"
            f"⚠️ 运行时修改，重启后恢复 .env 设置。"
        )
    elif target == "model":
        cfg.dotcharacter_model = value
        await matcher.finish(
            f"✅ 已切换模型为 **{value}**\n"
            f"⚠️ 运行时修改，重启后恢复 .env 设置。"
        )
    else:
        await matcher.finish(
            f"❌ 未知目标「{target}」。请使用 provider 或 model。"
        )


# ═══════════════════════════════════════════════
# 自由对话（群聊 @机器人 才触发）
# ═══════════════════════════════════════════════

async def _is_in_chat(event: Event) -> bool:
    await _ensure_initialized()
    if not _is_group_allowed(event):
        return False
    if _is_group(event) and not _is_at_bot(event):
        return False
    mgr = get_conversation_manager()
    return mgr.get_active_character(_scope_id(event)) is not None


chat_rule = Rule(_is_in_chat)
chat_matcher = on_message(rule=chat_rule, priority=99, block=False)


@chat_matcher.handle()
async def handle_chat(matcher: Matcher, event: Event):
    cfg = get_config()
    msg_text = event.get_plaintext().strip()
    if not msg_text:
        await matcher.finish()

    sid = _scope_id(event)
    user_name = _get_user_name(event)
    mgr = get_conversation_manager()
    slug = mgr.get_active_character(sid)

    if not slug:
        await matcher.finish()

    char = _characters.get(slug)
    if not char:
        mgr.clear_active_character(sid)
        await matcher.finish("⚠️ 角色数据丢失，请重新用 !角色切换 选择角色。")

    session = mgr.get_session(sid, slug)
    messages = [system_msg(char.combined_prompt)]
    for m in session.messages:
        messages.append(m)
    messages.append(user_msg(user_name, msg_text))

    try:
        reply = await chat_completion(
            cfg, messages, max_tokens=cfg.dotcharacter_max_tokens
        )
    except ValueError as e:
        await matcher.finish(f"❌ {e}")
    except RuntimeError as e:
        logger.error(f"[dotcharacter] LLM 调用失败: {e}")
        err_msg = str(e)
        if "超时" in err_msg or "timeout" in err_msg.lower():
            await matcher.finish(
                f"😵 {char.display_name} 响应超时了...\n"
                f"（API 连不上或太慢，等几秒再试试？）"
            )
        else:
            await matcher.finish(
                f"😵 {char.display_name} 暂时无法回应...\n（API 错误，请稍后再试）"
            )
    except Exception as e:
        logger.error(f"[dotcharacter] 未知错误: {e}")
        await matcher.finish(f"😵 出了点问题：{type(e).__name__}")

    session.add_user_message(msg_text)
    session.add_assistant_message(reply)
    session.trim(cfg.dotcharacter_max_history)

    await matcher.finish(reply)


# ═══════════════════════════════════════════════
# 插件生命周期
# ═══════════════════════════════════════════════

driver = get_driver()


@driver.on_startup
async def _on_startup():
    logger.info("[dotcharacter] 插件启动中...")
    # 懒加载 localstore（仅在 NoneBot 环境中可用）
    _get_store()
    await _ensure_initialized()
    cfg = get_config()
    admins = cfg.get_admin_qqs()
    groups = cfg.get_allowed_groups()
    roots = cfg.resolve_skills_paths()
    logger.info(
        f"[dotcharacter] 插件就绪，已加载 {len(_characters)} 个角色。"
        f" Provider={cfg.dotcharacter_provider}, Model={cfg.dotcharacter_model}"
    )
    logger.info(f"[dotcharacter] 角色目录 ({len(roots)} 个)：")
    for r in roots:
        logger.info(f"[dotcharacter]   - {r}")
    if admins:
        logger.info(f"[dotcharacter] 管理员：{admins}")
    if groups:
        logger.info(f"[dotcharacter] 允许的群组：{groups}")
    else:
        logger.info("[dotcharacter] 群组限制：未配置（所有群可用）")


@driver.on_shutdown
async def _on_shutdown():
    mgr = get_conversation_manager()
    cleaned = mgr.cleanup_stale(max_age_seconds=0)
    logger.info(f"[dotcharacter] 插件已关闭，清理了 {cleaned} 个会话。")
