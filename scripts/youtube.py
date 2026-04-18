#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube频道监控模块
使用RSS监控频道更新，优先提取字幕
"""

import os
import re
import json
import feedparser
import yt_dlp
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

from whisper_transcriber import WhisperTranscriber

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YouTubeMonitor:
    """YouTube频道监控器"""
    
    def __init__(self, config_path: str = "./内容监控/配置/博主列表.md"):
        self.config_path = config_path
        self.output_dir = "./内容监控/输出/YouTube"
        self.state_file = "./内容监控/log/YouTube状态.json"
        self.processed = self._load_state()
        
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    def _load_state(self) -> Dict:
        """加载已处理记录"""
        state_file = Path(self.state_file)
        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_state(self) -> None:
        """保存处理状态"""
        Path(self.state_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.processed, f, ensure_ascii=False, indent=2)
    
    def parse_channel_list(self) -> List[Dict]:
        """从配置文件解析频道列表"""
        channels = []
        current_section = None
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('## YouTube频道'):
                    current_section = 'youtube'
                elif line.startswith('##') or line.startswith('---'):
                    current_section = None
                elif current_section == 'youtube' and '|' in line and '频道' in line:
                    continue
                elif current_section == 'youtube' and '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 3 and parts[2]:
                        channel_id = self._extract_channel_id(parts[2])
                        if channel_id:
                            channels.append({
                                'name': parts[1],
                                'channel_id': channel_id,
                                'original': parts[2],
                                'note': parts[3] if len(parts) > 3 else ''
                            })
        
        return channels
    
    def _extract_channel_id(self, text: str) -> Optional[str]:
        """从文本提取YouTube频道ID"""
        text = text.strip()
        
        # 直接是UC开头的ID
        if text.startswith('UC') and len(text) == 24:
            return text
        
        # 从URL提取
        patterns = [
            r'/channel/(UC[a-zA-Z0-9_-]{22})',
            r'/@([a-zA-Z0-9_-]+)',
            r'youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})',
            r'youtube\.com/@([a-zA-Z0-9_-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return text if text else None
    
    def get_rss_url(self, channel_id: str) -> str:
        """生成频道RSS URL"""
        # @用户名格式需要先获取channel ID
        if not channel_id.startswith('UC'):
            return f"https://www.youtube.com/feeds/videos.xml?@{channel_id}"
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    def check_updates(self, channel_id: str) -> List[Dict]:
        """检查频道更新"""
        rss_url = self.get_rss_url(channel_id)
        
        try:
            feed = feedparser.parse(rss_url)
            updates = []
            
            for entry in feed.entries[:10]:
                video_id = self._extract_video_id(entry.get('id', ''))
                if video_id and video_id not in self.processed:
                    updates.append({
                        'id': video_id,
                        'title': entry.get('title', '无标题'),
                        'link': f"https://www.youtube.com/watch?v={video_id}",
                        'published': entry.get('published', ''),
                        'channel': feed.feed.get('title', ''),
                    })
            
            return updates
            
        except Exception as e:
            logger.error(f"获取YouTube更新失败: {e}")
            return []
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """从URL提取视频ID"""
        match = re.search(r'/watch\?v=([a-zA-Z0-9_-]{11})', url)
        if match:
            return match.group(1)
        
        # 也可能是shorts链接
        match = re.search(r'/shorts/([a-zA-Z0-9_-]{11})', url)
        if match:
            return match.group(1)
        
        return None
    
    def get_subtitles(self, video_url: str) -> Optional[Dict]:
        """获取字幕信息"""
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'writeautomaticsub': False,
            'listsubs': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                subtitles = info.get('subtitles', {})
                automatic_captions = info.get('automatic_captions', {})
                
                # 优先查找手动字幕
                for lang in ['zh-Hans', 'zh-CN', 'zh-Hant', 'zh', 'en']:
                    if lang in subtitles:
                        return {'type': 'manual', 'lang': lang, 'data': subtitles[lang]}
                
                # 其次查找自动字幕
                for lang in ['zh-Hans', 'zh-CN', 'zh-Hant', 'zh', 'en']:
                    if lang in automatic_captions:
                        return {'type': 'auto', 'lang': lang, 'data': automatic_captions[lang]}
                
                return None
                
        except Exception as e:
            logger.warning(f"获取字幕失败: {e}")
            return None
    
    def download_with_subtitles(
        self, 
        video_url: str, 
        output_path: str
    ) -> Optional[str]:
        """下载视频并提取字幕"""
        try:
            # 尝试下载字幕
            ydl_opts = {
                'quiet': True,
                'outtmpl': output_path + '.%(ext)s',
                'write-sub': True,
                'write-auto-sub': True,
                'sub-langs': 'zh-Hans,zh-CN,zh,en',
                'skip_download': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
            
            # 检查是否有字幕文件生成
            subtitle_path = output_path + '.zh-CN.srt'
            if not Path(subtitle_path).exists():
                subtitle_path = output_path + '.zh.srt'
            if not Path(subtitle_path).exists():
                subtitle_path = output_path + '.en.srt'
            if not Path(subtitle_path).exists():
                return None
            
            return subtitle_path
            
        except Exception as e:
            logger.warning(f"字幕下载失败: {e}")
            return None
    
    def transcribe_or_use_subtitles(
        self,
        video_url: str,
        video_info: Dict,
        transcriber: WhisperTranscriber
    ) -> str:
        """转录或使用字幕"""
        safe_title = "".join(c for c in video_info['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title[:50]
        
        temp_audio = Path(self.output_dir) / f"{safe_title}_temp.mp3"
        
        try:
            # 先尝试下载字幕
            subtitle_path = self.download_with_subtitles(
                video_url, 
                str(temp_audio.parent / safe_title)
            )
            
            if subtitle_path:
                # 使用字幕转为Markdown
                return self._subtitle_to_markdown(subtitle_path, video_info)
            
            # 无字幕，下载音频转录
            logger.info(f"无字幕，开始下载音频: {video_url}")
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(temp_audio),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(video_url, download=True)
            
            # 转录
            result = transcriber.transcribe_audio(str(temp_audio))
            
            # 生成Markdown
            return self._generate_markdown(result, video_info)
            
        except Exception as e:
            logger.error(f"处理失败: {e}")
            return f"# {video_info['title']}\n\n处理失败: {e}"
        
        finally:
            # 清理临时文件
            if temp_audio.exists():
                temp_audio.unlink()
    
    def _subtitle_to_markdown(self, subtitle_path: str, video_info: Dict) -> str:
        """将字幕文件转换为Markdown"""
        lines = []
        lines.append(f"# {video_info['title']}\n")
        lines.append(f"> 来源: {video_info.get('channel', 'YouTube')}\n")
        lines.append(f"> 发布时间: {video_info['published']}\n")
        lines.append(f"> 链接: {video_info['link']}\n")
        lines.append(f"> 格式: 字幕转录\n")
        lines.append("\n---\n\n")
        
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 清理SRT格式
        for line in content.split('\n'):
            line = line.strip()
            if line.isdigit() or '-->' in line:
                continue
            if line:
                lines.append(line + '\n\n')
        
        return ''.join(lines)
    
    def _generate_markdown(self, transcription: Dict, video_info: Dict) -> str:
        """生成转录Markdown"""
        lines = []
        lines.append(f"# {video_info['title']}\n")
        lines.append(f"> 来源: {video_info.get('channel', 'YouTube')}\n")
        lines.append(f"> 发布时间: {video_info['published']}\n")
        lines.append(f"> 链接: {video_info['link']}\n")
        lines.append(f"> 格式: Whisper AI转录\n")
        lines.append(f"> 音频语言: {transcription.get('language', 'zh')}\n")
        lines.append(f"> 时长: {transcription.get('duration', 0):.1f}秒\n")
        lines.append("\n---\n\n")
        
        # 时间轴
        lines.append("## 时间轴\n\n")
        for seg in transcription.get('segments', []):
            start = self._format_time(seg['start'])
            end = self._format_time(seg['end'])
            text = seg['text'].strip()
            lines.append(f"[{start} → {end}] {text}\n")
        
        # 完整文本
        lines.append("\n## 完整文本\n\n")
        lines.append(transcription.get('text', ''))
        
        return ''.join(lines)
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def save_result(self, content: str, video_info: Dict) -> str:
        """保存结果到文件"""
        safe_title = "".join(c for c in video_info['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title[:50]
        
        filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d')}.md"
        filepath = Path(self.output_dir) / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"保存完成: {filepath}")
        return str(filepath)
    
    def run(self, transcriber: Optional[WhisperTranscriber] = None) -> List[str]:
        """执行监控任务"""
        if transcriber is None:
            transcriber = WhisperTranscriber()
        
        channels = self.parse_channel_list()
        logger.info(f"找到 {len(channels)} 个YouTube频道订阅")
        
        results = []
        
        for channel in channels:
            logger.info(f"检查频道: {channel['name']}")
            updates = self.check_updates(channel['channel_id'])
            
            if not updates:
                logger.info(f"  无新内容")
                continue
            
            logger.info(f"  发现 {len(updates)} 个新内容")
            
            for video in updates:
                content = self.transcribe_or_use_subtitles(
                    video['link'], 
                    video, 
                    transcriber
                )
                filepath = self.save_result(content, video)
                results.append(filepath)
                
                # 更新状态
                self.processed[video['id']] = {
                    'title': video['title'],
                    'processed_at': datetime.now().isoformat(),
                    'path': filepath
                }
                self._save_state()
        
        return results


if __name__ == "__main__":
    monitor = YouTubeMonitor()
    results = monitor.run()
    print(f"\n处理完成，共处理 {len(results)} 个视频")
