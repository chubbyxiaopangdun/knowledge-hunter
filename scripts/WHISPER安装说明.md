# Whisper 安装说明

## 当前状态

以下依赖已安装：
- ✅ feedparser (RSS解析)
- ✅ httpx (HTTP请求)
- ✅ pytz (时区处理)
- ✅ yt-dlp (视频下载)
- ⏳ openai-whisper (语音转文字 - 待安装)

## Whisper 安装步骤

Whisper 需要 PyTorch 支持，首次安装需要下载约 2GB 文件。

### 方法一：国内镜像安装（推荐）

```bash
pip3 install torch --index-url https://download.pytorch.org/whl/cpu -i https://pypi.tuna.tsinghua.edu.cn/simple
pip3 install openai-whisper -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 方法二：分步安装

如果上述命令超时，可以分步执行：

```bash
# 1. 先安装CPU版PyTorch（约1.5GB）
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 2. 再安装Whisper
pip3 install openai-whisper
```

### 方法三：使用更小的模型

如果网络条件有限，可以安装精简版：

```bash
pip3 install faster-whisper
```

然后修改 `whisper_transcriber.py` 使用 faster-whisper。

## 验证安装

```bash
python3 -c "import whisper; print(whisper.__version__)"
```

## 首次使用

首次运行Whisper时会自动下载模型文件：
- tiny: ~39 MB
- base: ~74 MB (默认)
- small: ~244 MB

模型会保存到 `~/.cache/whisper/`

## 离线安装（备选方案）

如果网络问题持续存在，可以：

1. 在有良好网络的机器上下载wheel包
2. 拷贝到云电脑安装

### 预下载的wheel包地址：
- PyTorch CPU: https://download.pytorch.org/whl/torch_stable.html
- Whisper: https://pypi.org/simple/openai-whisper/

## 临时替代方案

在Whisper安装完成前，可以：
1. 使用各平台的字幕功能（YouTube/B站）
2. 系统会自动跳过需要Whisper转录的内容
3. 手动使用其他TTS服务生成文字稿
