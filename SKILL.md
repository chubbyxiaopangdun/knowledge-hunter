# 知识猎手 (Knowledge Hunter)

> 主动出击，精准捕获有价值的内容，转化为你的知识资产 🎯

**版本**: v2.0.0  
**更新时间**: 2026-04-18  
**状态**: 正式版 (stable)

---

## ⚠️ 安全声明与数据流向

**🔴 重要：使用本技能前，请务必了解以下安全风险**

### 外部服务依赖与数据流向

本技能的核心功能需要向以下**外部服务**发起网络请求：

| 服务类型 | 域名 | 用途 | 数据流向 | 风险等级 |
|---------|------|------|---------|---------|
| B站API | `api.bilibili.com` | 获取视频信息、字幕 | **可选发送**: Cookie(SESSDATA) **接收**: 视频数据 | 🟡 中 |
| YouTube | `youtube.com` | 获取视频信息 | **接收**: 视频数据 | 🟡 中 |
| 小宇宙 | `xiaoyuzhou.fm` | 获取播客信息、音频 | **接收**: 播客数据 | 🟡 中 |
| Twitter | `syndication.twitter.com` | 获取推文内容 | **接收**: 推文数据 | 🟡 中 |
| LLM服务 | 用户配置的API | 观点提取、选题生成 | **发送**: 转录文本 | 🟡 中 |

### ⚠️ B站登录态说明（可选）

如需访问B站私密视频，需要配置SESSDATA：
- ⚠️ 你的B站登录Cookie会被发送到 `api.bilibili.com`
- 🔐 **强烈建议使用B站小号**，不要使用主账号
- 🔄 定期更换SESSDATA（建议每月一次）
- 📝 如果账号出现异常，立即修改密码
- 💡 不配置SESSDATA也可以使用，仅支持公开内容

### 数据处理流程

```
1. 监控数据获取 → 向外部平台发起请求
2. 媒体下载 → 使用yt-dlp下载（本地处理）
3. 本地转录 → 使用Whisper本地模型（不外发）
4. 观点提取 → 可选：发送到LLM服务（需配置）
5. 飞书同步 → 可选：使用lark-cli上传（需安装）
```

### 使用须知

- ✅ 使用本技能即表示你了解并接受上述风险
- ✅ 请确保你有权访问和下载监控的内容
- ✅ 请遵守各平台的服务条款
- ❌ 不要使用本技能进行任何违法活动

### 安全建议

- 🔑 API密钥请妥善保管，不要硬编码在代码中
- 📝 首次使用前请阅读完整的安全说明
- 🛡️ 敏感内容请谨慎处理

---

## 技能概述

自动监控多平台内容更新，将音频/视频转成文字稿，并生成**选题发现报告**。

**支持平台：**
- 小宇宙（播客）
- YouTube（视频）
- 哔哩哔哩（视频）
- Twitter（推文）

---

## 核心升级：选题发现器 v1.2.0 🚀

从「内容消费」→「内容创作辅助」

**解决痛点**：内容创作者知道要做内容，但不知道写什么

### 新增功能

| 模块 | 脚本 | 功能 |
|------|------|------|
| 话题聚类器 | `topic_cluster.py` | 分析本周监控内容，识别热点话题，计算热度分数 |
| 选题生成器 | `topic_generator.py` | 基于热点话题和观点对比生成选题建议 |
| 内容关联器 | `content_relate.py` | 追踪用户选题的相关内容更新，发现续集机会 |
| 选题报告生成器 | `topic_report.py` | 组装周报格式的选题报告 |

### 选题报告格式

```
📋 本周选题发现 | 2026年第16周

🔥 热点话题（可追热点）
━━━━━━━━━━━━━━━━━━━

1️⃣ AI Agent创业
   📊 热度：讨论23条，本周增长180%
   💡 切入角度：
      - 技术视角：Agent的技术壁垒在哪里？
      - 商业视角：Agent创业的商业模式
   ✏️ 建议选题：「AI Agent创业的3个陷阱，踩中一个就死」

⚖️ 观点对比（可做对比内容）
━━━━━━━━━━━━━━━━━━━

「AI会取代程序员吗？」
🔴 张三：5年内AI会写90%代码，程序员要转型
🔵 李四：创造力无法替代，AI只是工具

📌 你的选题有更新（可追踪）
━━━━━━━━━━━━━━━━━━━

你之前做过「私域流量运营」
→ 本周相关更新：
  - 刘润：私域已死？真相是...
💡 建议选题：「私域流量运营一年后，我发现的3个真相」

📊 数据统计
━━━━━━━━━━━━━━━━━━━
- 本周监控：42条内容
- 发现热点：5个
- 生成选题：8个
- 追踪更新：3条
```

---

## 功能详解

### 1. 话题聚类器

**输入**：本周监控的所有内容（转录稿、观点）

**处理**：
- 关键词提取 + 相似度匹配进行话题聚类
- 热度分数 = 讨论量(40%) + 时效性(30%) + 互动(30%)
- 对比历史数据计算增长率

**输出**：Top 3-5 热点话题（含热度分数、切入角度）

### 2. 选题生成器

**输入**：热点话题 + 观点冲突

**处理**：
- 使用模板/LLM生成选题标题
- 提供切入角度建议
- 推荐内容格式和目标受众

**输出**：具体选题标题 + 切入角度 + 关键要点

### 3. 内容关联器

**输入**：用户历史选题库 + 本周新内容

**处理**：
- 关键词匹配计算相关性
- 分类更新类型（新增/观点/案例/数据）
- 生成追踪/续集建议

**输出**：选题追踪更新列表

### 4. 选题报告生成器

**组装**：
- 热点话题
- 观点对比
- 选题追踪
- 选题建议
- 统计数据
- 下周计划

**推送**：周日20:00自动推送

---

## 🎯 金句提取器 v1.4.0 ⭐ 最新升级

从「监控工具」升级为「素材工具」，自动从转录内容中提取金句，存入素材库供内容创作使用。

### 解决的问题

- 转录的内容无法直接用于创作
- 想要引用原文金句但找不到
- 积累的素材太多太杂难以整理

### 核心功能

| 模块 | 脚本 | 功能 |
|------|------|------|
| 金句提取器 | `quote_extractor.py` | 调用AI从转录文本中提取金句 |
| 素材库管理 | `quote_library.py` | 管理金句素材库，支持搜索和导出 |

### 金句提取流程

```
内容转录 → AI自动提取约20个金句 → 存入素材库 → 用户创作时提取使用
```

### 金句格式

每个金句包含：
- **原文**：完整的金句文本
- **主题标签**：AI自动识别的主题（创业/职场/AI等）
- **来源信息**：标题、作者、链接、平台
- **使用建议**：可选的使用场景提示

### 素材库目录结构

```
quotes/
├── all_quotes.md          # 全部金句汇总
├── by_topic/              # 按主题分类
│   ├── AI创业.md
│   ├── 个人成长.md
│   └── ...
└── metadata.json          # 元数据索引
```

### 配置选项

```bash
# 启用金句提取（默认关闭，向后兼容）
ENABLE_QUOTE_EXTRACTION=true

# 每个视频提取的金句数量
QUOTES_PER_VIDEO=20

# AI模型（默认gpt-4o-mini，性价比高）
QUOTE_MODEL=gpt-4o-mini

# 素材库存放目录
QUOTES_OUTPUT_DIR=./quotes
```

### 使用示例

```bash
# 命令行直接提取金句
python scripts/quote_extractor.py --file 输出/某视频.txt --title "视频标题"

# 查看素材库统计
python scripts/quote_library.py stats

# 按主题搜索
python scripts/quote_library.py list --topic AI

# 导出全部素材
python scripts/quote_library.py export --output my_quotes.md
```

### 注意事项

- ⚠️ 金句提取使用AI模型，会产生API费用
- 💡 建议使用 `gpt-4o-mini` 模型，性价比最高
- 🔄 默认关闭，如需启用请设置 `ENABLE_QUOTE_EXTRACTION=true`
- 📊 金句会自动按主题分类存储，方便后续查找使用

---

## 🎯 每日创意燃料 v2.0 ⭐ 核心升级（2026-04-18）

从「选题发现」升级为「创意燃料」，每天早上告诉你：**今天做什么内容**。

### 解决的问题

- 选题报告太「统计」不「行动」—— 不知道今天具体做什么
- 转录的内容无法直接用于创作
- 缺少「看完就能动手」的素材

### 核心功能

| 模块 | 脚本 | 功能 |
|------|------|------|
| 每日创意燃料 | `daily_fuel.py` | 每天生成「今日做什么」的行动建议 |
| 金句提取器 | `gold_sentence.py` | 从文本中提取有价值的引用金句 |
| Thread生成器 | `thread_generator.py` | 基于热点+金句生成可直接发布的内容 |

### 每日创意燃料格式

```
📋 今日创意燃料 | 2026-04-18 周六

🔥 今日热点（3个可追热点）
1️⃣ AI Agent创业
   - 热度：85/100 | 今日相关：12条
   - 建议选题：「AI Agent创业的3个陷阱」

💡 今日金句（5个可直接引用的素材）
「AI不会取代你，但会用AI的人会取代你」— 某CEO

✏️ 今日可做（1个可直接发布的Thread）
【Tweet 1/5】
{钩子}
...
```


### 金句提取器（gold_sentence.py）

**功能**：从任意文本中提取有价值的引用金句

**金句特征**：
1. 有独特观点（不是描述，是判断）
2. 语言有力（简洁有力）
3. 可独立引用（不需要上下文）
4. 字数适中（20-80字）
5. 有共鸣感（能引发认同）

**使用方式**：
```python
from gold_sentence import extract_gold_sentences

text = "...你的转录文本..."
sentences = extract_gold_sentences(text, count=5, use_llm=True)
# 输出：[{"text": "...", "source": "...", "speaker": "...", "usage": "..."}, ...]
```

### Thread生成器（thread_generator.py）

**功能**：基于热点话题和金句，生成可直接发布的Twitter Thread / 小红书文案

**支持格式**：
- `thread`：Twitter Thread（5条推文）
- `xiaohongshu`：小红书图文
- `article`：公众号文章大纲

**使用方式**：
```python
from thread_generator import generate_thread

topic = "AI Agent创业"
sentences = [{"text": "...", "source": "..."}]
content = generate_thread(topic, sentences, line_count=5, content_type="thread")
```

### 配置

```bash
# .env 文件中添加
FEISHU_ENABLED=true
OBSIDIAN_ENABLED=true
OBSIDIAN_VAULT_PATH=/path/to/vault
```

### 定时任务

```bash
# 每天早上9点生成创意燃料
0 9 * * * cd /path/to/knowledge-hunter && python scripts/daily_fuel.py
```

### 快速测试

```bash
# 手动生成今日创意燃料
python scripts/daily_fuel.py

# 测试金句提取
python scripts/gold_sentence.py

# 测试Thread生成
python scripts/thread_generator.py
```

---

## 目录结构

```
.skills/content-monitor/
├── scripts/                    # 核心脚本
│   ├── monitor.py             # 主监控脚本
│   ├── viewpoint_extractor.py # 观点提取器
│   ├── content_scorer.py      # 内容评分器
│   ├── conflict_detector.py   # 冲突检测器
│   ├── briefing_generator.py  # 简报生成器
│   ├── daily_briefing.py      # 定时推送任务
│   │
│   │   ⭐ v1.2.0 新增脚本 ⭐
│   ├── topic_cluster.py      # 🔥话题聚类器
│   ├── topic_generator.py    # 🔥选题生成器
│   ├── content_relate.py      # 🔥内容关联器
│   └── topic_report.py        # 🔥选题报告生成器
│   │
│   ├── xiaoyuzhou.py          # 小宇宙监控
│   ├── youtube.py             # YouTube监控
│   ├── bilibili.py            # B站监控
│   ├── twitter.py             # Twitter监控
│   ├── whisper_transcriber.py # Whisper转录
│   │
│   │   ⭐ v1.3.0 新增脚本 ⭐
│   ├── config.py              # 🔥知识库配置模块
│   ├── knowledge_base.py      # 🔥知识库工厂
│   ├── sync_to_obsidian.py    # 🔥Obsidian同步器
│   └── sync_to_feishu.py      # 飞书同步（已重构）
│   │
│   │   ⭐ v1.4.0 新增脚本 ⭐
│   ├── quote_extractor.py      # 🔥金句提取器
│   └── quote_library.py       # 🔥素材库管理器
│   │
│   │   ⭐ v2.0 新增脚本 ⭐
│   ├── daily_fuel.py          # 🔥每日创意燃料生成器
│   ├── gold_sentence.py       # 🔥金句提取器（新版）
│   └── thread_generator.py     # 🔥Thread生成器
│
├── 配置/
│   ├── 博主列表.md             # 监控目标配置
│   ├── 定时任务配置.md         # 定时任务设置
│   ├── LLM配置.json           # LLM配置
│   ├── 评分规则.json          # 评分规则
│   └── 选题配置.json          # ⭐选题配置 v1.2.0
│
├── templates/
│   ├── 博主列表.md             # 博主模板
│   ├── 每日简报模板.md        # 简报模板
│   ├── 历史选题库.md          # ⭐历史选题库 v1.2.0
│   └── 选题报告模板.md        # ⭐选题报告模板 v1.2.0
│
├── 选题库/
│   ├── 历史选题库.md           # ⭐用户选题记录 v1.2.0
│   └── 追踪记录.json          # ⭐追踪记录 v1.2.0
│
├── 缓存/
│   ├── 观点库/                # 观点数据库
│   ├── 评分库/                # 评分缓存
│   └── 话题库/                # ⭐话题历史 v1.2.0
│
├── quotes/                     # ⭐金句素材库 v1.4.0
│   ├── all_quotes.md          # 全部金句汇总
│   ├── by_topic/              # 按主题分类
│   │   ├── AI创业.md
│   │   ├── 个人成长.md
│   │   └── ...
│   └── metadata.json          # 元数据索引
│
├── 输出/
│   ├── 小宇宙/
│   ├── YouTube/
│   ├── B站/
│   ├── 简报/
│   ├── 选题报告/              # ⭐选题报告输出 v1.2.0
│   └── 选题建议/              # ⭐选题建议输出 v1.2.0
│
└── 日志/
```

---

## 快速开始

### 1. 初始化配置

```bash
# 复制并编辑配置
cp 配置/选题配置示例.json 配置/选题配置.json
cp templates/历史选题库.md 选题库/历史选题库.md
```

### 2. 添加你的选题

编辑 `选题库/历史选题库.md`，记录你做过的选题：

```markdown
| 日期 | 选题标题 | 状态 | 发布平台 | 备注 |
|------|----------|------|----------|------|
| 2026-04-01 | AI创业的3个机会 | 已发布 | 小红书 | 爆款 |
```

### 3. 生成选题报告

告诉诺诺：
- "帮我生成这周的选题报告"
- "生成本周的选题发现"
- "选题报告"

---

## 定时任务

### 每日简报（每日9:00）

告诉诺诺：
- "每天9点给我推送内容简报"

### 周选题报告（周日20:00）

告诉诺诺：
- "每周日晚上8点给我推送选题报告"
- "开启选题发现功能"

---

## 📚 知识库同步配置（v1.3.0）

### 支持的知识库

| 知识库 | 同步方式 | 配置难度 |
|--------|---------|---------|
| **飞书** | 通过 lark-cli 上传到知识库 | ⭐⭐ 需安装 lark-cli |
| **Obsidian** | 直接写入本地 vault 文件夹 | ⭐ 仅需指定路径 |

### 配置方法

#### 飞书知识库

1. **安装 lark-cli**（首次使用）
   ```bash
   # macOS
   brew install lark-cli
   
   # 或参考官方文档
   # https://github.com/nicepkg/lark-cli
   ```

2. **配置 .env**
   ```bash
   FEISHU_ENABLED=true
   FEISHU_WIKI_SPACE=你的知识库空间名
   FEISHU_ROOT_FOLDER=内容监控
   ```

#### Obsidian 知识库

1. **找到你的 vault 路径**
   - 在 Obsidian 中打开设置 → 关于 → 打开 vault 文件夹
   - 复制文件夹路径

2. **配置 .env**
   ```bash
   OBSIDIAN_ENABLED=true
   OBSIDIAN_VAULT_PATH=/Users/你的用户名/Documents/ObsidianVault
   OBSIDIAN_FOLDER=内容监控
   ```

### Obsidian 特性

同步到 Obsidian 的文件会自动：
- 添加 YAML frontmatter（日期、来源、标签、状态）
- 按 平台/日期_标题.md 格式命名
- 支持 `[[]]` 双链语法

示例 frontmatter：
```yaml
---
date: 2026-04-18
source: 小宇宙
tags: [播客, 转录, AI]
status: new
---
```

### 同时启用多个知识库

```bash
# .env
FEISHU_ENABLED=true
OBSIDIAN_ENABLED=true
```

系统会自动同步到所有启用的知识库~

---

## 配置说明

### 选题配置 (选题配置.json)

```json
{
  "report": {
    "push_time": "20:00",
    "push_day": "sunday"
  },
  "hot_topics": {
    "top_n": 5,
    "recency_days": 7
  },
  "topic_suggestions": {
    "suggestion_count": 8,
    "use_llm": false
  }
}
```

---

## 版本历史

| 版本 | 更新内容 |
|------|---------|
| **v1.3.0** | 多知识库支持：新增 Obsidian 同步、知识库工厂模式、向后兼容升级 |
| v1.2.0 | 新增选题发现器：话题聚类、选题生成、内容关联、选题报告 |
| v1.1.0 | 新增每日简报推送、观点提取、内容评分、冲突检测 |
| v1.0.0 | 基础监控功能（转录+飞书同步） |

---

## 📦 升级指南（v1.2.x → v1.3.0）

### 升级方式

**方式一：重新安装（推荐）**
从 GitHub 或虾评重新下载安装最新版本，覆盖原有文件即可。

**方式二：Git 拉取**
```bash
cd .skills/content-monitor
git pull origin main
```

### ⚠️ 重要：配置迁移

v1.3.0 对知识库同步进行了架构升级，需要更新配置：

#### 1. 创建 .env 文件

复制 `.env.example` 为 `.env`：
```bash
cp .env.example .env
```

#### 2. 启用知识库（按需配置）

**如果你之前使用飞书同步：**
```bash
# .env 文件中添加
FEISHU_ENABLED=true
FEISHU_WIKI_SPACE=my_library
FEISHU_ROOT_FOLDER=内容监控
```

**如果你想新增 Obsidian 同步：**
```bash
OBSIDIAN_ENABLED=true
OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
OBSIDIAN_FOLDER=内容监控
```

#### 3. 新增文件说明

| 文件 | 说明 |
|------|------|
| `scripts/config.py` | 知识库配置模块 |
| `scripts/knowledge_base.py` | 知识库工厂（统一管理多知识库） |
| `scripts/sync_to_obsidian.py` | Obsidian 同步器 |

### 向后兼容

- ✅ 默认不启用任何知识库同步
- ✅ 原有飞书配置方式仍然支持（但建议迁移到 .env）
- ✅ 监控、转录、观点提取等功能不受影响

---

## 📦 升级指南（v1.4.x → v2.0.0）

### 新增核心功能

| 功能 | 说明 |
|------|------|
| `daily_fuel.py` | 每日创意燃料生成器（核心新功能） |
| `gold_sentence.py` | 金句提取器（新版，替代quote_extractor.py） |
| `thread_generator.py` | Thread生成器（生成可直接发布的内容） |

### 升级方式

**方式一：重新克隆（推荐）**
```bash
git clone https://github.com/chubbyxiaopangdun/knowledge-hunter.git
```

**方式二：Git 拉取**
```bash
cd knowledge-hunter
git pull origin main
```

### v2.0 新功能配置

v2.0 不需要额外配置，所有功能默认关闭（如无内容则跳过）：

```bash
# .env 文件（已有则跳过）
cp .env.example .env

# 确保有LLM配置（如已配置则跳过）
# 编辑 配置/LLM配置.json 添加你的API Key
```

### 新增文件说明

| 文件 | 说明 |
|------|------|
| `scripts/daily_fuel.py` | 每日创意燃料生成器 |
| `scripts/gold_sentence.py` | 金句提取器（新版） |
| `scripts/thread_generator.py` | Thread生成器 |
| `templates/每日创意燃料模板.md` | 创意燃料模板 |

### 快速测试

```bash
# 手动生成今日创意燃料
python scripts/daily_fuel.py

# 测试金句提取
python scripts/gold_sentence.py

# 测试Thread生成
python scripts/thread_generator.py
```

### 定时任务（可选）

```bash
# 每天早上9点生成创意燃料
0 9 * * * cd /path/to/knowledge-hunter && python scripts/daily_fuel.py
```

---

## 获取帮助

告诉诺诺：
- "选题发现器使用帮助"
- "如何配置选题报告"
- "如何添加选题到选题库"
