<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-dotcharacter

_✨ 加载 dot-skill / colleague-skill 蒸馏角色，通过 QQ Bot 进行 AI 角色扮演对话 ✨_

<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/TonyLiangP2010405/nonebot-plugin-dotcharacter.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-dotcharacter">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-dotcharacter.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="python">

</div>

## 📖 介绍

与 Claude Code 使用 dot-skill 角色对话完全一致：

1. dot-skill / colleague-skill 从原材料（聊天记录、文档等）蒸馏出角色的 **SKILL.md**
2. SKILL.md 包含 PART A（工作能力）和 PART B（人物性格）
3. 对话时，系统提示词 = PART B 优先定态度 + PART A 供知识
4. LLM 按照系统提示词生成符合角色风格的回复

本插件做的事情：读取 SKILL.md → 构造系统提示词 → 管理多用户对话历史 → 调用 LLM API → 返回角色回复。

### 特性

- 🎭 支持 celebrity / colleague / relationship 三类角色
- 🤖 支持 **9 个 LLM Provider** 预设（DeepSeek / OpenAI / Kimi / Qwen / Zhipu / SiliconFlow / Groq / Ollama / Custom）
- 📂 多目录角色扫描，支持 dot-skill 和 colleague-skill 两种格式
- 🔥 热加载角色，无需重启
- 💬 群聊 @机器人 触发对话，命令无需 @
- 👑 管理员权限控制（命令仅管理员可用）
- 🧠 私聊会话独立，群聊会话按群共享
- 🔄 LLM API 超时自动重试（3次，指数退避）
- ⚡ 连接池优化，避免长时间运行后连接失效

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-dotcharacter

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-dotcharacter
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-dotcharacter
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-dotcharacter
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_dotcharacter"]

</details>

## ⚙️ 配置

在 nonebot2 项目的 `.env` 文件中添加下表中的配置

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| DOTCHARACTER_PROVIDER | 否 | custom | LLM Provider 预设：deepseek / openai / kimi / qwen / zhipu / siliconflow / groq / ollama / custom |
| DOTCHARACTER_API_KEY | 是 | 无 | API Key |
| DOTCHARACTER_API_BASE | 否 | https://api.openai.com/v1 | API 地址（provider=custom 时有效） |
| DOTCHARACTER_MODEL | 否 | gpt-4o-mini | 模型名称 |
| DOTCHARACTER_SKILLS_PATH | 否 | 自动查找 | 角色目录路径（逗号分隔） |
| DOTCHARACTER_MAX_HISTORY | 否 | 20 | 对话历史条数 |
| DOTCHARACTER_TEMPERATURE | 否 | 0.8 | 生成温度 (0.0-2.0) |
| DOTCHARACTER_MAX_TOKENS | 否 | 1024 | 最大 Token 数 |
| DOTCHARACTER_TIMEOUT | 否 | 60 | API 超时秒数 |
| DOTCHARACTER_ADMIN_QQ | 否 | 无 | 管理员 QQ 号（逗号分隔） |
| DOTCHARACTER_ALLOWED_GROUPS | 否 | 无 | 允许的群号（逗号分隔，留空全部允许） |

### LLM Provider 预设

| Provider | 默认模型 | Base URL |
|:--------:|:--------:|:--------:|
| deepseek | deepseek-chat | https://api.deepseek.com |
| openai | gpt-4o | https://api.openai.com/v1 |
| kimi | moonshot-v1-8k | https://api.moonshot.cn/v1 |
| qwen | qwen-plus | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| zhipu | glm-4-plus | https://open.bigmodel.cn/api/paas/v4 |
| siliconflow | Qwen/Qwen2.5-72B-Instruct | https://api.siliconflow.cn/v1 |
| groq | llama-3.3-70b-versatile | https://api.groq.com/openai/v1 |
| ollama | llama3 | http://localhost:11434/v1 |
| custom | gpt-4o-mini | 自定义 |

## 📂 角色目录结构

`DOTCHARACTER_SKILLS_PATH` 指向的是 **skills 根目录**，插件会扫描其下的一级子目录。目录结构必须如下：

```
skills/                          ← DOTCHARACTER_SKILLS_PATH 指向这里
├── celebrity/                   ← 一级子目录必须是这三类之一
│   └── xiao_xiao_tao_zi_yo/     ← 角色文件夹（文件夹名即 slug）
│       ├── SKILL.md             ← 主技能文件（必须）
│       ├── meta.json            ← 元数据（可选）
│       └── persona.md           ← 人物性格（可选，优先于 SKILL.md 的 PART B）
├── colleague/
│   └── xxx/
└── relationship/
    └── xxx/
```

**注意**：角色文件夹必须放在 `celebrity/`、`colleague/` 或 `relationship/` 下，直接放在 skills 根目录不会被识别。

## ⚠️ 重要提示

### NoneBot 命令前缀

本插件的命令以 `!` 开头（如 `!角色列表`），请确保你的 `.env` 中已配置：

```env
COMMAND_START=["!", "/"]
```

否则 NoneBot 不会识别命令。

### 群聊会话机制

- **群聊**：管理员执行 `!角色切换` 后，**全群共享同一个会话**。任何群成员 @机器人 发消息都会进入同一个对话历史。
- **私聊**：每个用户与角色的对话历史是独立的。

### 指令表

| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:-----:|:----:|:----:|:----:|:----:|
| `!角色列表` | 管理员 | 否 | 群聊/私聊 | 列出所有可用角色 |
| `!角色切换 <名称>` | 管理员 | 否 | 群聊/私聊 | 切换到指定角色 |
| `!角色退出` | 管理员 | 否 | 群聊/私聊 | 退出当前对话 |
| `!重置对话` | 管理员 | 否 | 群聊/私聊 | 清空对话历史 |
| `!角色信息 [名称]` | 管理员 | 否 | 群聊/私聊 | 查看角色详情 |
| `!角色路径` | 管理员 | 否 | 群聊/私聊 | 查看当前扫描的目录 |
| `!角色刷新` | 管理员 | 否 | 群聊/私聊 | 重新扫描角色目录 |
| `!角色导入 add <路径>` | 管理员 | 否 | 群聊/私聊 | 添加角色目录 |
| `!模型切换` | 管理员 | 否 | 群聊/私聊 | 查看当前 LLM 配置 |
| `!模型切换 provider <名称>` | 管理员 | 否 | 群聊/私聊 | 切换 LLM Provider |
| `!模型切换 model <名称>` | 管理员 | 否 | 群聊/私聊 | 切换模型 |
| `!设置限流 <次数>` | 管理员 | 否 | 群聊/私聊 | 设置 10 分钟内每人最多对话次数（0 = 关闭） |
| `!限流状态` | 管理员 | 否 | 群聊/私聊 | 查看当前限流设置和已用次数 |
| 直接对话 | 所有人 | 群聊需要 | 群聊/私聊 | 与角色对话 |

## 🔗 相关项目

- [colleague-skill](https://github.com/titanwings/colleague-skill) — dot-skill 角色蒸馏工具，支持 celebrity / colleague / relationship 三类角色

## 📄 许可证

MIT
