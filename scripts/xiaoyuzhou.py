#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小宇宙播客监控模块
解析RSS订阅，下载音频并转录
支持全网资源对比（v1.5.0）
"""

import os
import re
import feedparser
import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

from whisper_transcriber import WhisperTranscriber

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class XiaoyuzhouMonitor:
    """小宇宙播客监控器"""
    
    # 平台限制错误的关键字（v1.5.0新增）
    RESTRICTION_ERRORS = [
        "403", "forbidden", "access denied", "blocked",
        "not available", "unavailable", "private",
        "This content is not available", "这条内容不可用",
        "视频加载失败", "音频加载失败", "获取不到",
        "Download is disabled", "download disabled",
        "Sign in to view", "登录后可查看",
        "copyright", "版权", "已下架", "已删除",
        "HTTP 403", "HTTP 404", "status_code: 403"
    ]
    
    def __init__(self, config_path: str = "./内容监控/配置/博主列表.md"):
        self.config_path = config_path
        self.output_dir = "./内容监控/输出/小宇宙"
        self.state_file = "./内容监控/日志/小宇宙状态.json"
        self.processed = self._load_state()
        
        # Fallback配置（v1.5.0新增）
        self._fallback_handler = None
        self._fallback_transcriber = None
        
        # 创建输出目录
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    def _init_fallback_handler(self):
        """初始化 Fallback 处理器（延迟加载）"""
        if self._fallback_handler is None:
            try:
                from fallback_handler import FallbackHandler, TranscribeWithFallback
                self._fallback_handler = FallbackHandler()
                
                # 检查是否启用
                if not self._fallback_handler.enable_fallback:
                    logger.info("Fallback搜索已禁用")
                    return
                    
                logger.info("FallbackHandler 初始化成功")
            except ImportError as e:
                logger.warning(f"无法导入FallbackHandler: {e}")
                self._fallback_handler = None
    
    def detect_restriction_error(self, error: Exception) -> bool:
        """检测是否为平台限制错误（v1.5.0新增）
        
        Args:
            error: 异常对象
            
        Returns:
            True if platform restriction detected, False otherwise
        """
        error_str = str(error).lower()
        
        for keyword in self.RESTRICTION_ERRORS:
            if keyword.lower() in error_str:
                logger.warning(f"检测到平台限制: {keyword}")
                return True
        
        # 检查HTTP状态码
        if hasattr(error, 'response'):
            status_code = getattr(error.response, 'status_code', 0)
            if status_code in [403, 404, 451]:
                return True
        
        return False
    
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
        """下载音频并转录（v1.5.0增强：支持Fallback）"""
        audio_url = self.extract_audio_url(item)
        
        if not audio_url:
            logger.warning(f"未找到音频URL: {item['title']}")
            return None
        
        # 提取播客名（用于Fallback搜索）
        podcast_name = feed_name
        
        try:
            # 尝试直接转录
            return self._download_and_transcribe_direct(
                item, audio_url, transcriber, feed_name
            )
            
        except Exception as primary_error:
            logger.warning(f"主资源转录失败: {primary_error}")
            
            # 检测是否为平台限制错误
            if not self.detect_restriction_error(primary_error):
                # 非平台限制错误，直接返回失败
                logger.error(f"非平台限制错误: {primary_error}")
                return None
            
            # 平台限制，尝试Fallback
            return self._try_fallback_transcribe(
                item, transcriber, podcast_name, primary_error
            )
    
    def _download_and_transcribe_direct(
        self,
        item: Dict,
        audio_url: str,
        transcriber: WhisperTranscriber,
        feed_name: str
    ) -> Optional[str]:
        """直接下载并转录"""
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
        return self._save_transcription(item, result, filename, feed_name, source_note=None)
    
    def _try_fallback_transcribe(
        self,
        item: Dict,
        transcriber: WhisperTranscriber,
        podcast_name: str,
        original_error: Exception
    ) -> Optional[str]:
        """尝试使用Fallback资源转录（v1.5.0新增）"""
        logger.info("检测到平台限制，开始搜索替代资源...")
        
        # 延迟初始化Fallback处理器
        self._init_fallback_handler()
        
        if self._fallback_handler is None:
            logger.warning("FallbackHandler不可用，跳过替代资源搜索")
            return None
        
        if not self._fallback_handler.enable_fallback:
            logger.info("Fallback搜索已禁用")
            return None
        
        # 搜索替代资源
        title = item['title']
        alternatives = self._fallback_handler.search_alternative_sources(
            title=title,
            author=podcast_name,
            content_type='audio'
        )
        
        if not alternatives:
            logger.warning("未找到替代资源")
            self._log_fallback_attempt(item, None, original_error, "no_alternatives")
            return None
        
        logger.info(f"找到 {len(alternatives)} 个替代资源")
        
        # 选择最佳替代
        best = self._fallback_handler.get_best_alternative(alternatives, verify=True)
        
        if not best:
            logger.warning("没有可用的替代资源")
            self._log_fallback_attempt(item, alternatives, original_error, "all_verification_failed")
            return None
        
        # 使用替代资源转录
        try:
            download_url = self._fallback_handler.get_download_url(best)
            logger.info(f"使用替代资源: {best.get('platform_name')} - {download_url}")
            
            # 下载并转录（使用yt-dlp兼容的方式）
            temp_audio = self._download_from_alternative(download_url, item['title'])
            
            if not temp_audio:
                raise Exception("替代资源下载失败")
            
            # 转录
            result = transcriber.transcribe_audio(str(temp_audio))
            
            # 保存Markdown，标注来源变更
            audio_ext = Path(temp_audio).suffix
            filename = f"{item['title'][:50]}_{datetime.now().strftime('%Y%m%d')}{audio_ext}"
            
            source_note = (
                f"\n> ⚠️ 资源来源变更: 原小宇宙资源被限制，"
                f"使用 {best.get('platform_name')} 替代资源\n"
            )
            
            path = self._save_transcription(
                item, result, filename, podcast_name, source_note=source_note
            )
            
            # 清理临时文件
            if temp_audio.exists():
                temp_audio.unlink()
            
            self._log_fallback_attempt(item, best, original_error, "success", best)
            
            return path
            
        except Exception as e:
            logger.warning(f"替代资源转录失败: {e}")
            self._log_fallback_attempt(item, best, original_error, "transcribe_failed")
            return None
    
    def _download_from_alternative(self, url: str, title: str) -> Optional[Path]:
        """从替代资源下载音频"""
        try:
            import yt_dlp
            
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title[:50]
            
            output_template = str(Path(self.output_dir) / f"{safe_title}_fallback.%(ext)s")
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    ext = info.get('ext', 'mp3')
                    return Path(output_template.replace('%(ext)s', ext))
            
        except Exception as e:
            logger.error(f"替代资源下载失败: {e}")
            return None
    
    def _save_transcription(
        self,
        item: Dict,
        result: Dict,
        filename: str,
        feed_name: str,
        source_note: Optional[str] = None
    ) -> str:
        """保存转录结果"""
        md_filename = Path(filename).with_suffix('.md')
        md_filepath = Path(self.output_dir) / md_filename
        
        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {item['title']}\n\n")
            f.write(f"> 来源: {feed_name}\n")
            f.write(f"> 发布时间: {item['published']}\n")
            f.write(f"> 链接: {item['link']}\n")
            if source_note:
                f.write(source_note)
            f.write("\n---\n\n")
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
    
    def _log_fallback_attempt(
        self,
        item: Dict,
        result: any,
        original_error: Exception,
        status: str,
        alternative: Optional[Dict] = None
    ) -> None:
        """记录Fallback尝试日志"""
        try:
            import json
            from pathlib import Path
            
            log_file = Path("./内容监控/日志/fallback_attempts.jsonl")
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            event = {
                'item_id': item['id'],
                'title': item['title'],
                'original_error': str(original_error),
                'status': status,
                'alternative': {
                    'platform': alternative.get('platform') if alternative else None,
                    'url': alternative.get('url') if alternative else None,
                },
                'timestamp': datetime.now().isoformat()
            }
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
                
        except Exception as e:
            logger.warning(f"记录Fallback日志失败: {e}")
    
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
