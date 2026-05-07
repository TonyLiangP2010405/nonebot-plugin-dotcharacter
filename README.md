# nonebot-plugin-dotcharacter

> 🎭 加载 dot-skill / colleague-skill 蒸馏的角色，通过 QQ Bot 进行 AI 角色扮演对话

## 原理

与 Claude Code 使用 dot-skill 角色对话完全一致：

1. dot-skill / colleague-skill 从原材料（聊天记录、文档等）蒸馏出角色的 **SKILL.md**
2. SKILL.md 包含 PART A（工作能力）和 PART B（人物性格）
3. 对话时，系统提示词 = PART B 优先定态度 + PART A 供知识
4. LLM 按照系统提示词生成符合角色风格的回复

本插件做的事情：读取 SKILL.md → 构造系统提示词 → 管理多用户对话历史 → 调用 LLM API → 返回角色回复。

## 安装

```bash
pip install nonebot-plugin-dotcharacter
```

或使用 NB-CLI：

```bash
nb plugin install nonebot-plugin-dotcharacter
```

## 配置

在 NoneBot 的 `.env` 文件中添加：

```env
# LLM（支持所有 OpenAI 兼容接口）
DOTCHARACTER_PROVIDER=deepseek           # openai/deepseek/kimi/qwen/zhipu/siliconflow/groq/ollama/custom
DOTCHARACTER_API_KEY=sk-your-api-key
DOTCHARACTER_MODEL=deepseek-chat

# 角色目录（逗号分隔多个路径）
# 不设置则自动查找 Claude Code / Hermes / OpenClaw / colleague-skill 默认位置
DOTCHARACTER_SKILLS_PATH=C:/path/to/characters/skills

# 可选
DOTCHARACTER_MAX_HISTORY=20              # 对话历史条数
DOTCHARACTER_TEMPERATURE=0.8
DOTCHARACTER_MAX_TOKENS=1024
DOTCHARACTER_TIMEOUT=60

# 权限（可选）
DOTCHARACTER_ADMIN_QQ=123456789          # 管理员 QQ 号，逗号分隔
DOTCHARACTER_ALLOWED_GROUPS=987654321    # 允许的群号，逗号分隔。留空则全部允许
```

## 使用方法

### 管理员命令

| 命令 | 说明 |
|------|------|
| `!角色列表` | 列出所有可用角色 |
| `!角色切换 <名称>` | 切换到指定角色 |
| `!角色退出` | 退出当前对话 |
| `!重置对话` | 清空对话历史 |
| `!角色信息 [名称]` | 查看角色详情 |
| `!角色路径` | 查看当前扫描的目录 |
| `!角色刷新` | 重新扫描角色目录 |
| `!角色导入 add <路径>` | 添加角色目录 |
| `!模型切换` | 查看当前 LLM 配置 |
| `!模型切换 provider <名称>` | 切换 LLM Provider |
| `!模型切换 model <名称>` | 切换模型 |

### 角色对话

切换到角色后，**直接发送消息**即可对话。
群聊中需要 **@机器人** 触发对话。

## 角色目录结构

插件自动扫描以下目录：
- `DOTCHARACTER_SKILLS_PATH` 指定的路径（逗号分隔）
- `~/.claude/skills/dot-skill/skills/`
- `~/.hermes/skills/dot-skill/skills/`
- `~/colleague-skill/skills/`
- 以及其他常见位置

期望目录结构（dot-skill / colleague-skill 输出）：

```
skills/
├── colleague/<slug>/SKILL.md + meta.json + persona.md
├── relationship/<slug>/SKILL.md + meta.json + persona.md
└── celebrity/<slug>/SKILL.md + meta.json + persona.md
```

把蒸馏好的角色文件放到任意目录，用 `!角色导入 add` 或配置 `.env` 即可加载。

## 支持的 LLM

| Provider | 说明 |
|----------|------|
| `deepseek` | DeepSeek（默认推荐） |
| `openai` | OpenAI |
| `kimi` | Moonshot Kimi |
| `qwen` | 阿里通义千问 |
| `zhipu` | 智谱 GLM |
| `siliconflow` | SiliconFlow |
| `groq` | Groq |
| `ollama` | 本地 Ollama |
| `custom` | 自定义 OpenAI 兼容接口 |

## 权限模型

- 命令（`!角色*` 等）：仅管理员可用（`DOTCHARACTER_ADMIN_QQ`）
- 角色扮演对话：所有用户可用
- 群聊 @机器人 才触发对话（命令不需要 @）

## 依赖

- Python >= 3.9
- nonebot2 >= 2.3.0
- nonebot-adapter-onebot >= 0.3.0
- httpx >= 0.24.0
- pyyaml >= 6.0
- nonebot-plugin-localstore >= 0.4.0

## License

MIT
