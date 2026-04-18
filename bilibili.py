#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站监控模块
使用API监控UP主更新，提取CC字幕
支持公开内容和登录态（需要SESSDATA）
"""

import os
import re
import json
import httpx
import yt_dlp
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

from whisper_transcriber import WhisperTranscriber

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# B站Cookie配置（可选）
# 用于访问需要登录的视频
# 获取方法：登录bilibili.com → F12 → Application → Cookies → SESSDATA
# 建议：使用小号，不要使用主账号
SESSDATA = os.environ.get('BILIBILI_SESSDATA', '')  # 从环境变量读取


class BilibiliMonitor:
    """B站UP主监控器"""
    
    def __init__(self, config_path: str = "./内容监控/配置/博主列表.md"):
        self.config_path = config_path
        self.output_dir = "./内容监控/输出/B站"
        self.state_file = "./内容监控/log/哔哩哔哩状态.json"
        self.processed = self._load_state()
        
        # B站API
        self.api_base = "https://api.bilibili.com"
        
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
    
    def parse_up_list(self) -> List[Dict]:
        """从配置文件解析UP主列表"""
        ups = []
        current_section = None
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('## B站UP主'):
                    current_section = 'bilibili'
                elif line.startswith('##') or line.startswith('---'):
                    current_section = None
                elif current_section == 'bilibili' and '|' in line and 'UID' in line:
                    continue
                elif current_section == 'bilibili' and '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 3 and parts[2].isdigit():
                        ups.append({
                            'name': parts[1],
                            'uid': parts[2],
                            'note': parts[3] if len(parts) > 3 else ''
                        })
        
        return ups
    
    def get_up_info(self, uid: str) -> Optional[Dict]:
        """获取UP主信息"""
        url = f"{self.api_base}/x/space/wbi/arc/search"
        params = {
            'mid': uid,
            'ps': 1,
            'pn': 1,
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(url, params=params, timeout=10)
                data = response.json()
                
                if data.get('code') == 0:
                    return data.get('data', {}).get('lists', [])
                return None
        except Exception as e:
            logger.error(f"获取UP主信息失败: {e}")
            return None
    
    def check_updates(self, uid: str) -> List[Dict]:
        """检查UP主更新"""
        url = f"{self.api_base}/x/space/wbi/arc/search"
        params = {
            'mid': uid,
            'ps': 10,
            'pn': 1,
            'order': 'pubdate',
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(url, params=params, timeout=10)
                data = response.json()
            
            if data.get('code') != 0:
                logger.error(f"API错误: {data}")
                return []
            
            videos = data.get('data', {}).get('list', {}).get('vlist', [])
            updates = []
            
            for video in videos:
                bvid = video.get('bvid', '')
                if bvid and bvid not in self.processed:
                    updates.append({
                        'bvid': bvid,
                        'aid': video.get('aid'),
                        'title': video.get('title', '无标题'),
                        'link': f"https://www.bilibili.com/video/{bvid}",
                        'published': self._format_time(video.get('created', 0)),
                        'duration': video.get('length', '00:00'),
                        'author': video.get('author', ''),
                        'description': video.get('description', ''),
                    })
            
            return updates
            
        except Exception as e:
            logger.error(f"获取B站更新失败: {e}")
            return []
    
    def _format_time(self, timestamp: int) -> str:
        """格式化时间戳"""
        if timestamp:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        return ''
    
    def get_subtitles(self, bvid: str) -> Optional[Dict]:
        """获取字幕信息"""
        url = f"{self.api_base}/x/web-interface/view"
        params = {'bvid': bvid}
        
        try:
            with httpx.Client() as client:
                response = client.get(url, params=params, timeout=10)
                data = response.json()
            
            if data.get('code') != 0:
                return None
            
            video_data = data.get('data', {})
            subtitle_url = None
            subtitle_type = 'CC字幕'
            
            # 检查字幕
            subtitles = video_data.get('subtitle', {}).get('subtitles', [])
            if subtitles:
                first_sub = subtitles[0]
                subtitle_url = first_sub.get('subtitle_url')
                subtitle_type = first_sub.get('lan_doc', 'CC字幕')
            
            return {
                'url': subtitle_url,
                'type': subtitle_type,
                'title': video_data.get('title', ''),
            }
            
        except Exception as e:
            logger.warning(f"获取字幕信息失败: {e}")
            return None
    
    def download_subtitle(self, subtitle_url: str) -> Optional[str]:
        """下载字幕文件"""
        if not subtitle_url:
            return None
        
        try:
            # B站字幕是ASS格式
            if not subtitle_url.startswith('http'):
                subtitle_url = f"https:{subtitle_url}"
            
            with httpx.Client() as client:
                response = client.get(subtitle_url, timeout=10)
                response.raise_for_status()
            
            # 保存为临时ASS文件
            temp_path = Path(self.output_dir) / f"temp_subtitle.ass"
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            return str(temp_path)
            
        except Exception as e:
            logger.warning(f"字幕下载失败: {e}")
            return None
    
    def ass_to_text(self, ass_path: str) -> str:
        """将ASS字幕转换为纯文本（带时间轴）"""
        lines = []
        in_text = False
        
        with open(ass_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                if line == '[Events]':
                    in_text = True
                    continue
                
                if in_text and line.startswith('Dialogue:'):
                    # 解析Dialogue行
                    parts = line.split(',', 9)
                    if len(parts) >= 10:
                        start_time = parts[1].strip()
                        end_time = parts[2].strip()
                        text = parts[9].strip()
                        
                        # 移除ASS标签
                        text = re.sub(r'\{[^}]*\}', '', text)
                        
                        if text:
                            lines.append(f"[{start_time} → {end_time}] {text}")
        
        return '\n'.join(lines)
    
    def process_video(
        self, 
        video: Dict, 
        transcriber: WhisperTranscriber
    ) -> str:
        """处理视频"""
        bvid = video['bvid']
        
        # 尝试获取字幕
        subtitle_info = self.get_subtitles(bvid)
        
        if subtitle_info and subtitle_info.get('url'):
            # 有字幕，下载字幕并转换
            ass_path = self.download_subtitle(subtitle_info['url'])
            
            if ass_path:
                content = self._generate_markdown_with_subtitle(
                    self.ass_to_text(ass_path),
                    video,
                    subtitle_info['type']
                )
                
                # 删除临时文件
                Path(ass_path).unlink()
                
                return content
        
        # 无字幕，使用yt-dlp下载音频转录
        logger.info(f"无字幕，开始转录: {video['title']}")
        
        safe_title = "".join(c for c in video['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title[:50]
        
        temp_audio = Path(self.output_dir) / f"{safe_title}_temp.mp3"
        
        try:
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
                ydl.extract_info(video['link'], download=True)
            
            result = transcriber.transcribe_audio(str(temp_audio))
            content = self._generate_markdown(result, video)
            
        except Exception as e:
            logger.error(f"处理失败: {e}")
            content = self._generate_error_markdown(video, str(e))
        
        finally:
            if temp_audio.exists():
                temp_audio.unlink()
        
        return content
    
    def _generate_markdown_with_subtitle(
        self, 
        subtitle_text: str, 
        video: Dict,
        subtitle_type: str
    ) -> str:
        """生成带字幕的Markdown"""
        lines = []
        lines.append(f"# {video['title']}\n")
        lines.append(f"> UP主: {video['author']}\n")
        lines.append(f"> 发布时间: {video['published']}\n")
        lines.append(f"> 时长: {video['duration']}\n")
        lines.append(f"> 链接: {video['link']}\n")
        lines.append(f"> 字幕类型: {subtitle_type}\n")
        lines.append(f"> 格式: CC字幕提取\n")
        lines.append("\n---\n\n")
        lines.append(subtitle_text)
        
        return ''.join(lines)
    
    def _generate_markdown(self, transcription: Dict, video: Dict) -> str:
        """生成转录Markdown"""
        lines = []
        lines.append(f"# {video['title']}\n")
        lines.append(f"> UP主: {video['author']}\n")
        lines.append(f"> 发布时间: {video['published']}\n")
        lines.append(f"> 时长: {video['duration']}\n")
        lines.append(f"> 链接: {video['link']}\n")
        lines.append(f"> 格式: Whisper AI转录\n")
        lines.append(f"> 音频语言: {transcription.get('language', 'zh')}\n")
        lines.append(f"> 转录时长: {transcription.get('duration', 0):.1f}秒\n")
        lines.append("\n---\n\n")
        
        # 时间轴
        lines.append("## 时间轴\n\n")
        for seg in transcription.get('segments', []):
            start = self._format_time_whisper(seg['start'])
            end = self._format_time_whisper(seg['end'])
            text = seg['text'].strip()
            lines.append(f"[{start} → {end}] {text}\n")
        
        # 完整文本
        lines.append("\n## 完整文本\n\n")
        lines.append(transcription.get('text', ''))
        
        return ''.join(lines)
    
    def _generate_error_markdown(self, video: Dict, error: str) -> str:
        """生成错误Markdown"""
        lines = []
        lines.append(f"# {video['title']}\n")
        lines.append(f"> UP主: {video['author']}\n")
        lines.append(f"> 发布时间: {video['published']}\n")
        lines.append(f"> 链接: {video['link']}\n")
        lines.append("\n---\n\n")
        lines.append(f"**处理失败**: {error}\n")
        return ''.join(lines)
    
    def _format_time_whisper(self, seconds: float) -> str:
        """格式化Whisper时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def save_result(self, content: str, video: Dict) -> str:
        """保存结果"""
        safe_title = "".join(c for c in video['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
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
        
        ups = self.parse_up_list()
        logger.info(f"找到 {len(ups)} 个B站UP主订阅")
        
        results = []
        
        for up in ups:
            logger.info(f"检查UP主: {up['name']} (UID: {up['uid']})")
            updates = self.check_updates(up['uid'])
            
            if not updates:
                logger.info(f"  无新内容")
                continue
            
            logger.info(f"  发现 {len(updates)} 个新内容")
            
            for video in updates:
                content = self.process_video(video, transcriber)
                filepath = self.save_result(content, video)
                results.append(filepath)
                
                # 更新状态
                self.processed[video['bvid']] = {
                    'title': video['title'],
                    'processed_at': datetime.now().isoformat(),
                    'path': filepath
                }
                self._save_state()
        
        return results


if __name__ == "__main__":
    monitor = BilibiliMonitor()
    results = monitor.run()
    print(f"\n处理完成，共处理 {len(results)} 个视频")
