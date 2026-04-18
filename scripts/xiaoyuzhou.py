#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小宇宙播客监控模块
解析RSS订阅，下载音频并转录
"""

import os
import feedparser
import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

from whisper_transcriber import WhisperTranscriber

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class XiaoyuzhouMonitor:
    """小宇宙播客监控器"""
    
    def __init__(self, config_path: str = "./内容监控/配置/博主列表.md"):
        self.config_path = config_path
        self.output_dir = "./内容监控/输出/小宇宙"
        self.state_file = "./内容监控/日志/小宇宙状态.json"
        self.processed = self._load_state()
        
        # 创建输出目录
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    def _load_state(self) -> Dict:
        """加载已处理记录"""
        import json
        state_file = Path(self.state_file)
        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_state(self) -> None:
        """保存处理状态"""
        import json
        Path(self.state_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.processed, f, ensure_ascii=False, indent=2)
    
    def parse_rss_list(self) -> List[Dict]:
        """从配置文件解析RSS列表"""
        feeds = []
        current_section = None
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('## 小宇宙播客'):
                    current_section = 'xiaoyuzhou'
                elif line.startswith('##') or line.startswith('---'):
                    current_section = None
                elif current_section == 'xiaoyuzhou' and '|' in line and 'RSS' in line:
                    continue  # 跳过表头
                elif current_section == 'xiaoyuzhou' and '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 3 and 'http' in parts[2]:
                        feeds.append({
                            'name': parts[1],
                            'url': parts[2],
                            'note': parts[3] if len(parts) > 3 else ''
                        })
        
        return feeds
    
    def check_updates(self, feed_url: str) -> List[Dict]:
        """检查RSS更新"""
        try:
            feed = feedparser.parse(feed_url)
            updates = []
            
            for entry in feed.entries[:10]:  # 只检查最新10条
                entry_id = entry.get('id', entry.get('link', ''))
                
                if entry_id not in self.processed:
                    updates.append({
                        'id': entry_id,
                        'title': entry.get('title', '无标题'),
                        'link': entry.get('link', ''),
                        'published': entry.get('published', ''),
                        'enclosures': entry.get('enclosures', []),
                    })
            
            return updates
            
        except Exception as e:
            logger.error(f"解析RSS失败 {feed_url}: {e}")
            return []
    
    def extract_audio_url(self, entry: Dict) -> Optional[str]:
        """从条目中提取音频URL"""
        enclosures = entry.get('enclosures', [])
        
        # 优先查找音频文件
        audio_types = ['audio/mpeg', 'audio/mp3', 'audio/m4a', 'audio/wav']
        
        for enc in enclosures:
            if enc.get('type', '') in audio_types:
                return enc.get('href') or enc.get('url')
        
        # 回退：查找任何包含音频扩展名的链接
        for enc in enclosures:
            url = enc.get('href') or enc.get('url', '')
            if any(ext in url.lower() for ext in ['.mp3', '.m4a', '.wav', '.ogg']):
                return url
        
        return None
    
    def download_and_transcribe(
        self, 
        item: Dict, 
        transcriber: WhisperTranscriber,
        feed_name: str
    ) -> Optional[str]:
        """下载音频并转录"""
        audio_url = self.extract_audio_url(item)
        
        if not audio_url:
            logger.warning(f"未找到音频URL: {item['title']}")
            return None
        
        try:
            # 下载音频
            logger.info(f"下载音频: {audio_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ContentMonitor/1.0)'
            }
            
            audio_ext = '.mp3'
            if '.m4a' in audio_url.lower():
                audio_ext = '.m4a'
            
            safe_title = "".join(c for c in item['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title[:50]  # 限制长度
            
            filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d')}{audio_ext}"
            filepath = Path(self.output_dir) / filename
            
            with httpx.stream("GET", audio_url, headers=headers, timeout=60.0) as response:
                response.raise_for_status()
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
            
            # 转录
            logger.info(f"开始转录: {filepath}")
            result = transcriber.transcribe_audio(str(filepath))
            
            # 保存Markdown
            md_filename = filename.replace(audio_ext, '.md')
            md_filepath = Path(self.output_dir) / md_filename
            
            with open(md_filepath, 'w', encoding='utf-8') as f:
                f.write(f"# {item['title']}\n\n")
                f.write(f"> 来源: {feed_name}\n")
                f.write(f"> 发布时间: {item['published']}\n")
                f.write(f"> 链接: {item['link']}\n\n")
                f.write("---\n\n")
                f.write(result['markdown'])
            
            logger.info(f"转录完成: {md_filepath}")
            
            # 更新状态
            self.processed[item['id']] = {
                'title': item['title'],
                'transcribed_at': datetime.now().isoformat(),
                'md_path': str(md_filepath)
            }
            self._save_state()
            
            return str(md_filepath)
            
        except Exception as e:
            logger.error(f"下载转录失败: {e}")
            return None
    
    def run(self, transcriber: Optional[WhisperTranscriber] = None) -> List[str]:
        """执行监控任务"""
        if transcriber is None:
            transcriber = WhisperTranscriber()
        
        feeds = self.parse_rss_list()
        logger.info(f"找到 {len(feeds)} 个小宇宙播客订阅")
        
        results = []
        
        for feed in feeds:
            logger.info(f"检查播客: {feed['name']}")
            updates = self.check_updates(feed['url'])
            
            if not updates:
                logger.info(f"  无新内容")
                continue
            
            logger.info(f"  发现 {len(updates)} 个新内容")
            
            for item in updates:
                md_path = self.download_and_transcribe(item, transcriber, feed['name'])
                if md_path:
                    results.append(md_path)
        
        return results


if __name__ == "__main__":
    monitor = XiaoyuzhouMonitor()
    results = monitor.run()
    print(f"\n处理完成，共转录 {len(results)} 个播客")
