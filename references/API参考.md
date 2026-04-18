# Content Monitor API 参考

## 主监控脚本 (monitor.py)

### 用法

```python
from monitor import ContentMonitor

# 初始化监控器
monitor = ContentMonitor()

# 执行监控
results = monitor.run()

# 只监控特定平台
results = monitor.run(platforms=['xiaoyuzhou', 'youtube'])
```

### 返回值

```python
{
    'success': True,
    'platforms': {
        'xiaoyuzhou': {
            'new_content': 2,
            'transcribed': 2,
            'files': ['xxx.md', 'yyy.md']
        },
        'youtube': {
            'new_content': 1,
            'transcribed': 1,
            'files': ['zzz.md']
        }
    },
    'synced_to_feishu': True
}
```

---

## 小宇宙监控 (xiaoyuzhou.py)

### 用法

```python
from xiaoyuzhou import XiaoyuzhouMonitor

# 初始化
monitor = XiaoyuzhouMonitor()

# 测试单个节目
result = monitor.transcribe_episode(
    url='https://www.xiaoyuzhoufm.com/episode/xxx',
    output_dir='./输出/小宇宙测试'
)

# 监控RSS更新
new_episodes = monitor.check_updates()
```

### 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| url | str | 小宇宙单集链接 |
| output_dir | str | 输出目录 |
| model | str | Whisper模型大小 (tiny/base/small) |
| with_timestamp | bool | 是否保留时间轴 |

### 返回值

```python
{
    'title': '节目标题',
    'podcast': '播客名',
    'duration': 7200,  # 秒
    'transcript_file': 'path/to/transcript.md',
    'word_count': 15000,
    'segments': 450
}
```

---

## Whisper转录器 (whisper_transcriber.py)

### 用法

```python
from whisper_transcriber import WhisperTranscriber

# 初始化（默认base模型）
transcriber = WhisperTranscriber(model='base')

# 转录音频文件
result = transcriber.transcribe(
    audio_path='audio.m4a',
    language='zh',
    with_timestamp=True
)

# 保存结果
transcriber.save_transcript(
    result,
    output_path='transcript.md',
    format='markdown'
)
```

### 模型选择

```python
# 快速转录（牺牲质量）
transcriber = WhisperTranscriber(model='tiny')

# 平衡质量和速度（推荐）
transcriber = WhisperTranscriber(model='base')

# 高质量转录
transcriber = WhisperTranscriber(model='small')
```

### 长音频处理

```python
# 自动分段处理长音频
result = transcriber.transcribe_long_audio(
    audio_path='long_audio.m4a',
    segment_duration=300,  # 每段5分钟
    language='zh'
)
```

---

## 飞书同步 (sync_to_feishu.py)

### 用法

```python
from sync_to_feishu import FeishuSync

# 初始化
sync = FeishuSync()

# 同步单个文件
result = sync.upload_file(
    file_path='transcript.md',
    folder_name='内容监控/小宇宙'
)

# 批量同步
results = sync.sync_folder(
    folder_path='./输出/',
    target_folder='内容监控'
)

# 创建索引文档
sync.create_index(
    title='内容监控 - 小宇宙',
    items=[
        {'name': '节目1', 'url': '...'},
        {'name': '节目2', 'url': '...'}
    ]
)
```

### 认证状态检查

```python
# 检查是否已授权
if sync.is_authenticated():
    print("已授权")
else:
    # 获取授权链接
    auth_url = sync.get_auth_url()
    print(f"请授权: {auth_url}")
```

---

## YouTube监控 (youtube.py)

### 用法

```python
from youtube import YouTubeMonitor

# 初始化
monitor = YouTubeMonitor()

# 获取频道最新视频
videos = monitor.get_latest_videos(channel_id='UCxxxxxxx', limit=5)

# 下载并转录
result = monitor.download_and_transcribe(
    video_url='https://www.youtube.com/watch?v=xxx',
    prefer_subtitle=True  # 优先使用官方字幕
)
```

### 字幕提取

```python
# 提取官方字幕
subtitle = monitor.extract_subtitle(video_url)
if subtitle:
    # 有官方字幕，直接保存
    monitor.save_subtitle(subtitle, output_path)
else:
    # 无字幕，需要转录
    result = monitor.transcribe_video(video_url)
```

---

## B站监控 (bilibili.py)

### 用法

```python
from bilibili import BilibiliMonitor

# 初始化
monitor = BilibiliMonitor()

# 获取UP主最新视频
videos = monitor.get_latest_videos(uid=12345678, limit=5)

# 下载并转录
result = monitor.download_and_transcribe(
    bvid='BV1xxx',
    prefer_cc=True  # 优先使用CC字幕
)
```

---

## Twitter监控 (twitter.py)

### 用法

```python
from twitter import TwitterMonitor

# 初始化
monitor = TwitterMonitor()

# 获取用户推文
tweets = monitor.get_user_tweets(username='elonmusk', limit=20)

# 保存推文
monitor.save_tweets(
    tweets,
    output_path='./输出/Twitter/elonmusk/',
    format='markdown'
)
```

---

## 配置读取

### 读取博主列表

```python
from monitor import ConfigReader

config = ConfigReader('./内容监控/配置/博主列表.md')

# 获取小宇宙列表
xiaoyuzhou_feeds = config.get_xiaoyuzhou_feeds()
# 返回: [('给女孩的商业第一课', 'https://feed.xyzfm.space/xxx'), ...]

# 获取YouTube列表
youtube_channels = config.get_youtube_channels()
# 返回: [('Ali Abdaal', 'UCxxxxxxx'), ...]

# 获取B站列表
bilibili_ups = config.get_bilibili_ups()
# 返回: [('影视飓风', '12345678'), ...]
```

---

## 错误处理

### 常见错误

```python
try:
    result = monitor.transcribe_episode(url)
except MemoryError:
    # 内存不足，尝试分段处理
    result = monitor.transcribe_long_audio(url, segment_duration=300)
except NetworkError:
    # 网络错误，稍后重试
    time.sleep(60)
    result = monitor.transcribe_episode(url)
except Exception as e:
    print(f"转录失败: {e}")
```

### 重试机制

```python
from monitor import retry_on_failure

@retry_on_failure(max_retries=3, delay=60)
def transcribe_with_retry(url):
    return monitor.transcribe_episode(url)
```
