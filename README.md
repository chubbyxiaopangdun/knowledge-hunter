# 知识猎手 (Knowledge Hunter) 🎯

<div align="center">

**主动出击，精准捕获有价值的内容，转化为你的知识资产**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](https://github.com)

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [安装指南](#-安装指南) • [使用文档](#-使用文档) • [贡献指南](#-贡献指南)

</div>

---

## 📖 项目简介

**知识猎手** 是一个开源的多平台内容监控与转录系统，可以自动监控小宇宙播客、YouTube、B站、Twitter等平台的内容更新，将音视频内容转换为带时间轴的文字稿，并同步到飞书知识库。

**核心理念**：
- 🆓 **完全免费** - 使用 OpenAI Whisper 开源模型，本地运行，无 API 费用
- 🎯 **精准捕获** - 优先提取官方字幕，无字幕时自动使用 Whisper 转录
- ⚡ **自动化** - 每日自动检查更新，自动转录，自动同步
- 📚 **知识沉淀** - 自动提取观点，生成结构化知识库

---

## ✨ 功能特性

### 支持平台

| 平台 | 功能 | 状态 | 说明 |
|------|------|------|------|
| 🎙️ 小宇宙 | 播客转录 | ✅ 已验证 | 支持 RSS 订阅，自动下载音频转录 |
| 📺 YouTube | 视频转录 | ✅ 已验证 | 优先提取 CC 字幕，支持多语言 |
| 📱 B站 | 视频转录 | ⚠️ 需登录态 | 提取 CC 字幕，需配置 SESSDATA |
| 🐦 Twitter | 推文抓取 | 📋 待完善 | 支持用户动态追踪 |

### 核心功能

#### 1. 音视频转录
- **Whisper 本地转录**：支持 tiny/base/small/medium 模型
- **字幕优先策略**：优先提取官方字幕，无字幕时使用 Whisper
- **时间轴保留**：生成带时间戳的文字稿，方便定位
- **长音频处理**：自动分段处理，避免内存溢出

#### 2. 多平台监控
- **RSS 订阅监控**：支持小宇宙等播客平台
- **API 监控**：YouTube Data API、B站 API
- **定时检查**：每日自动检查更新
- **增量更新**：只处理新增内容

#### 3. 知识库同步
- **飞书知识库**：自动同步文档和文件
- **索引生成**：自动创建内容索引
- **观点提取**：AI 自动提取有价值观点
- **定期汇总**：每周生成内容汇总报告

#### 4. 观点提取
- **自动分类**：按主题自动归类观点
- **金句提取**：提取有价值的核心观点
- **实操建议**：生成可执行的行动建议
- **结构化输出**：生成 Markdown 格式报告

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- FFmpeg（音频处理）
- 8GB+ 内存（推荐，用于 Whisper 转录）

### 一键安装

```bash
# 克隆仓库
git clone https://github.com/chubby-developer/knowledge-hunter.git
cd knowledge-hunter

# 安装依赖
pip install -r requirements.txt

# 安装 Whisper 模型
pip install openai-whisper

# 运行安装脚本
bash scripts/setup.sh
```

### 基本使用

#### 1. 转录单个播客

```python
from scripts.xiaoyuzhou import XiaoyuzhouMonitor

monitor = XiaoyuzhouMonitor()
result = monitor.transcribe_episode("https://www.xiaoyuzhoufm.com/episode/xxx")
print(f"转录完成：{result['output_file']}")
```

#### 2. 转录 YouTube 视频

```python
from scripts.youtube import YouTubeMonitor

monitor = YouTubeMonitor()
result = monitor.transcribe_video("https://www.youtube.com/watch?v=xxx")
print(f"转录完成：{result['output_file']}")
```

#### 3. 同步到飞书

```python
from scripts.sync_to_feishu import FeishuSync

sync = FeishuSync()
sync.sync_document(
    file_path="./output/transcript.md",
    folder_name="播客转录"
)
```

---

## 📦 安装指南

### 详细安装步骤

#### 1. 系统依赖

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
下载 FFmpeg 并添加到系统 PATH。

#### 2. Python 依赖

```bash
pip install -r scripts/requirements.txt
```

主要依赖：
- `openai-whisper` - 语音转录
- `yt-dlp` - YouTube/B站视频下载
- `feedparser` - RSS 解析
- `requests` - HTTP 请求

#### 3. Whisper 模型选择

| 模型 | VRAM | 速度 | 准确度 | 推荐场景 |
|------|------|------|--------|----------|
| tiny | ~1GB | 最快 | 一般 | 快速预览 |
| base | ~1GB | 快 | 良好 | 日常使用（推荐） |
| small | ~2GB | 中等 | 优秀 | 高质量需求 |
| medium | ~5GB | 慢 | 优秀 | 专业用途 |

---

## 📚 使用文档

### 目录结构

```
knowledge-hunter/
├── README.md                 # 本文档
├── SKILL.md                  # 技能完整文档
├── requirements.txt          # Python 依赖
│
├── scripts/                  # 核心脚本
│   ├── monitor.py           # 主监控程序
│   ├── xiaoyuzhou.py        # 小宇宙处理
│   ├── youtube.py           # YouTube 处理
│   ├── bilibili.py          # B站处理
│   ├── twitter.py           # Twitter 处理
│   ├── whisper_transcriber.py  # Whisper 转录器
│   ├── sync_to_feishu.py    # 飞书同步
│   └── check_dependencies.py   # 依赖检查
│
├── references/               # 参考文档
│   ├── API参考.md           # API 详细说明
│   ├── 最佳实践.md          # 使用建议
│   ├── 使用案例.md          # 实际案例
│   └── 常见问题.md          # FAQ
│
└── templates/                # 配置模板
    ├── 博主列表.md          # 监控目标配置
    ├── 定时任务配置.md      # Cron 配置
    └── 每日监控任务.md      # 每日任务模板
```

### 定时任务配置

```bash
# 添加到 crontab
crontab -e

# 每天早上 8 点执行监控
0 8 * * * cd /path/to/knowledge-hunter && python scripts/monitor.py --daily

# 每周日生成周报
0 9 * * 0 cd /path/to/knowledge-hunter && python scripts/monitor.py --weekly-report
```

---

## 📊 实测数据

### 转录性能

| 音频时长 | 模型 | 处理时间 | 输出行数 | 硬件 |
|----------|------|----------|----------|------|
| 123分钟 | base | ~20分钟 | 5056行 | CPU 8核 |
| 60分钟 | base | ~10分钟 | ~2500行 | CPU 8核 |
| 30分钟 | tiny | ~3分钟 | ~1200行 | CPU 4核 |

### 准确度测试

| 平台 | 测试用例 | 通过率 | 说明 |
|------|----------|--------|------|
| YouTube | 10/10 | 100% | 字幕提取完美 |
| 小宇宙 | 1/1 | 100% | 123分钟播客转录成功 |
| B站 | 3/5 | 60% | 需登录态获取字幕 |

---

## 🔧 高级配置

### B站登录态配置

B站视频下载需要登录态，获取方法：

1. 登录 B站网页版
2. 打开开发者工具 → Application → Cookies
3. 找到 `SESSDATA` 的值
4. 设置环境变量：

```bash
export BILIBILI_SESSDATA="your_sessdata_here"
```

### Whisper 模型配置

```python
# 配置文件中的模型选择
WHISPER_MODEL = "base"  # tiny/base/small/medium
WHISPER_DEVICE = "cpu"  # cpu/cuda
WHISPER_LANGUAGE = "zh"  # 自动检测语言
```

---

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 代码规范

- 使用 Black 格式化代码
- 添加类型注解
- 编写单元测试
- 更新相关文档

### 报告问题

发现 Bug 或有功能建议？请创建 Issue。

---

## 📄 许可证

本项目采用 MIT 许可证。

---

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 开源语音识别模型
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 强大的视频下载工具
- [飞书开放平台](https://open.feishu.cn/) - 知识库同步支持

---

## 📮 联系方式

- **作者**: 诺诺 (AI Agent) × chubby
- **虾评主页**: https://xiaping.coze.site/skill/ba5802fb-3b11-4556-9cdb-0e743c14a9eb

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐ Star 支持一下！**

Made with ❤️ by 诺诺

</div>
