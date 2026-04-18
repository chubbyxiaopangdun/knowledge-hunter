#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全网资源对比模块 (v1.5.0)
当小宇宙等平台限制音频转录时，自动寻找可转录的替代资源
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import quote_plus
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 脚本目录
SCRIPT_DIR = Path(__file__).parent
LOG_DIR = SCRIPT_DIR.parent / "日志"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class FallbackHandler:
    """全网资源对比处理器"""
    
    # 平台限制错误的关键字
    RESTRICTION_KEYWORDS = [
        "403", "forbidden", "access denied", "blocked",
        "not available", "unavailable", "private",
        "This content is not available", "这条内容不可用",
        "视频加载失败", "音频加载失败", "获取不到",
        "Download is disabled", "download disabled",
        "Sign in to view", "登录后可查看",
        "copyright", "版权", "已下架", "已删除"
    ]
    
    # 替代平台配置
    PLATFORM_CONFIG = {
        "youtube": {
            "name": "YouTube",
            "search_url": "https://www.youtube.com/results?search_query={query}",
            "api_url": "https://www.googleapis.com/youtube/v3/search",
            "transcribable": True,
            "priority": 1,  # 优先级，数字越小越高
        },
        "bilibili": {
            "name": "B站",
            "search_url": "https://search.bilibili.com/all?keyword={query}",
            "api_url": "https://api.bilibili.com/x/web-interface/search/type",
            "transcribable": True,
            "priority": 2,
        },
        "apple_podcasts": {
            "name": "Apple Podcasts",
            "search_url": "https://podcasts.apple.com/search?term={query}",
            "transcribable": True,
            "priority": 3,
        },
        "spotify": {
            "name": "Spotify",
            "search_url": "https://open.spotify.com/search/{query}",
            "transcribable": True,
            "priority": 4,
        },
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化 Fallback 处理器
        
        Args:
            config: 配置字典，包含以下可选键：
                - enable_fallback_search: 是否启用搜索（默认True）
                - fallback_platforms: 要搜索的平台列表
                - max_search_results: 最大搜索结果数
                - fallback_timeout: 超时时间（秒）
                - search_log_path: 搜索日志路径
        """
        self.config = config or {}
        
        # 从配置读取或使用默认值
        self.enable_fallback = self.config.get(
            'ENABLE_FALLBACK_SEARCH',
            os.getenv('ENABLE_FALLBACK_SEARCH', 'true').lower() == 'true'
        )
        
        platforms_str = self.config.get(
            'FALLBACK_PLATFORMS',
            os.getenv('FALLBACK_PLATFORMS', 'youtube,bilibili,apple_podcasts')
        )
        self.fallback_platforms = [p.strip() for p in platforms_str.split(',')]
        
        self.max_search_results = int(self.config.get(
            'FALLBACK_MAX_RESULTS',
            os.getenv('FALLBACK_MAX_RESULTS', '10')
        ))
        
        self.timeout = int(self.config.get(
            'FALLBACK_TIMEOUT',
            os.getenv('FALLBACK_TIMEOUT', '300')
        ))
        
        # 搜索日志
        self.log_file = LOG_DIR / "fallback_search.log"
        
        # 缓存搜索结果（避免重复搜索）
        self._search_cache: Dict[str, List[Dict]] = {}
        
        logger.info(f"FallbackHandler 初始化完成")
        logger.info(f"  - 启用搜索: {self.enable_fallback}")
        logger.info(f"  - 搜索平台: {self.fallback_platforms}")
        logger.info(f"  - 超时时间: {self.timeout}s")
    
    def detect_platform_restriction(self, error: Exception, context: Optional[Dict] = None) -> bool:
        """检测是否为平台限制错误
        
        Args:
            error: 异常对象
            context: 上下文信息（可选）
            
        Returns:
            True if platform restriction detected, False otherwise
        """
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # 检查错误消息中是否包含限制关键字
        for keyword in self.RESTRICTION_KEYWORDS:
            if keyword.lower() in error_str:
                logger.warning(f"检测到平台限制: {keyword}")
                self._log_search_event({
                    "event": "restriction_detected",
                    "keyword": keyword,
                    "error": str(error),
                    "context": context,
                    "timestamp": datetime.now().isoformat()
                })
                return True
        
        # 检查特定错误类型
        restriction_errors = [
            "httpx.HTTPStatusError",  # 403, 404等HTTP错误
            "urllib.error.HTTPError",
            "aiohttp.ClientResponseError",
        ]
        
        if error_type in restriction_errors:
            # 进一步检查状态码
            if hasattr(error, 'response'):
                status_code = getattr(error.response, 'status_code', 0)
                if status_code in [403, 404, 451]:
                    logger.warning(f"检测到HTTP状态码限制: {status_code}")
                    return True
        
        return False
    
    def search_alternative_sources(
        self, 
        title: str, 
        author: Optional[str] = None,
        content_type: str = "audio"
    ) -> List[Dict]:
        """全网搜索替代资源
        
        Args:
            title: 内容标题
            author: 作者/播客名（可选）
            content_type: 内容类型 (audio/video)
            
        Returns:
            搜索结果列表，每项包含 platform, url, title, relevance 等字段
        """
        if not self.enable_fallback:
            logger.info("Fallback搜索已禁用")
            return []
        
        # 生成缓存键
        cache_key = f"{title}:{author}:{content_type}"
        if cache_key in self._search_cache:
            logger.info(f"使用缓存的搜索结果: {title[:30]}...")
            return self._search_cache[cache_key]
        
        # 构建搜索关键词
        search_query = self._build_search_query(title, author)
        logger.info(f"开始搜索替代资源: {search_query}")
        
        results = []
        
        # 按优先级搜索各平台
        for platform in self.fallback_platforms:
            if platform not in self.PLATFORM_CONFIG:
                continue
            
            config = self.PLATFORM_CONFIG[platform]
            
            try:
                platform_results = self._search_platform(
                    platform, 
                    search_query, 
                    content_type
                )
                results.extend(platform_results)
                
            except Exception as e:
                logger.warning(f"搜索 {config['name']} 失败: {e}")
                self._log_search_event({
                    "event": "platform_search_failed",
                    "platform": platform,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
        
        # 按优先级排序
        results.sort(key=lambda x: x.get('priority', 999))
        
        # 限制结果数量
        results = results[:self.max_search_results]
        
        # 记录搜索结果
        self._log_search_event({
            "event": "search_completed",
            "query": search_query,
            "results_count": len(results),
            "results": results,
            "timestamp": datetime.now().isoformat()
        })
        
        # 缓存结果
        self._search_cache[cache_key] = results
        
        return results
    
    def _build_search_query(self, title: str, author: Optional[str] = None) -> str:
        """构建搜索关键词"""
        # 清理标题，移除特殊字符
        clean_title = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', title)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        if author:
            # 作者 + 标题（更精准）
            return f"{author} {clean_title}"
        return clean_title
    
    def _search_platform(
        self, 
        platform: str, 
        query: str, 
        content_type: str
    ) -> List[Dict]:
        """在指定平台搜索"""
        config = self.PLATFORM_CONFIG[platform]
        results = []
        
        if platform == "youtube":
            results = self._search_youtube(query, content_type)
        elif platform == "bilibili":
            results = self._search_bilibili(query, content_type)
        elif platform == "apple_podcasts":
            results = self._search_apple_podcasts(query)
        elif platform == "spotify":
            results = self._search_spotify(query)
        
        # 添加平台信息和优先级
        for result in results:
            result['platform'] = platform
            result['platform_name'] = config['name']
            result['priority'] = config['priority']
        
        return results
    
    def _search_youtube(self, query: str, content_type: str) -> List[Dict]:
        """搜索YouTube"""
        try:
            # 使用YouTube Data API
            api_key = os.getenv('YOUTUBE_API_KEY')
            
            if api_key:
                # 优先使用API
                return self._search_youtube_api(query, api_key)
            else:
                # 回退到网页搜索（仅返回搜索URL，不验证可用性）
                search_url = self.PLATFORM_CONFIG["youtube"]["search_url"].format(
                    query=quote_plus(query)
                )
                return [{
                    "url": search_url,
                    "title": f"YouTube搜索: {query[:50]}",
                    "relevance": 0.8,
                    "verified": False
                }]
                
        except Exception as e:
            logger.warning(f"YouTube搜索失败: {e}")
            return []
    
    def _search_youtube_api(self, query: str, api_key: str) -> List[Dict]:
        """使用YouTube API搜索"""
        try:
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': self.max_search_results,
                'key': api_key
            }
            
            response = httpx.get(
                'https://www.googleapis.com/youtube/v3/search',
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get('items', []):
                video_id = item['id']['videoId']
                results.append({
                    'url': f'https://www.youtube.com/watch?v={video_id}',
                    'title': item['snippet']['title'],
                    'relevance': 0.9,
                    'verified': True,
                    'video_id': video_id
                })
            
            return results
            
        except Exception as e:
            logger.warning(f"YouTube API搜索失败: {e}")
            return []
    
    def _search_bilibili(self, query: str, content_type: str) -> List[Dict]:
        """搜索B站"""
        try:
            params = {
                'search_key': query,
                'page': 1,
                'page_size': self.max_search_results,
                'platform': 'web',
                'search_type': 'video' if content_type == 'video' else 'video'
            }
            
            response = httpx.get(
                'https://api.bilibili.com/x/web-interface/search/type',
                params=params,
                timeout=30,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; ContentMonitor/1.0)'
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 0:
                return []
            
            results = []
            for item in data.get('data', {}).get('result', []):
                bvid = item.get('bvid', '')
                if bvid:
                    results.append({
                        'url': f'https://www.bilibili.com/video/{bvid}',
                        'title': item.get('title', '').replace('<em class="keyword">', '').replace('</em>', ''),
                        'relevance': 0.85,
                        'verified': True,
                        'bvid': bvid,
                        'duration': item.get('duration', '')
                    })
            
            return results
            
        except Exception as e:
            logger.warning(f"B站搜索失败: {e}")
            return []
    
    def _search_apple_podcasts(self, query: str) -> List[Dict]:
        """搜索Apple Podcasts"""
        try:
            search_url = self.PLATFORM_CONFIG["apple_podcasts"]["search_url"].format(
                query=quote_plus(query)
            )
            
            return [{
                'url': search_url,
                'title': f"Apple Podcasts搜索: {query[:50]}",
                'relevance': 0.7,
                'verified': False
            }]
            
        except Exception as e:
            logger.warning(f"Apple Podcasts搜索失败: {e}")
            return []
    
    def _search_spotify(self, query: str) -> List[Dict]:
        """搜索Spotify"""
        try:
            search_url = self.PLATFORM_CONFIG["spotify"]["search_url"].format(
                query=quote_plus(query)
            )
            
            return [{
                'url': search_url,
                'title': f"Spotify搜索: {query[:50]}",
                'relevance': 0.6,
                'verified': False
            }]
            
        except Exception as e:
            logger.warning(f"Spotify搜索失败: {e}")
            return []
    
    def verify_source_available(self, url: str, platform: str) -> Tuple[bool, Optional[str]]:
        """验证资源是否可转录
        
        Args:
            url: 资源URL
            platform: 平台名称
            
        Returns:
            (is_available, error_message)
        """
        try:
            if platform == "youtube":
                return self._verify_youtube(url)
            elif platform == "bilibili":
                return self._verify_bilibili(url)
            else:
                # 其他平台默认可用（需进一步验证）
                return True, None
                
        except Exception as e:
            return False, str(e)
    
    def _verify_youtube(self, url: str) -> Tuple[bool, Optional[str]]:
        """验证YouTube资源可用性"""
        try:
            # 提取视频ID
            video_id = None
            if 'youtube.com/watch' in url:
                match = re.search(r'[?&]v=([^&]+)', url)
                if match:
                    video_id = match.group(1)
            elif 'youtu.be/' in url:
                match = re.search(r'youtu\.be/([^?]+)', url)
                if match:
                    video_id = match.group(1)
            
            if not video_id:
                return False, "无法解析YouTube视频ID"
            
            # 检查视频是否可用
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ContentMonitor/1.5)'
            }
            
            # 尝试获取视频页面
            response = httpx.get(
                f'https://www.youtube.com/watch?v={video_id}',
                headers=headers,
                timeout=30,
                follow_redirects=True
            )
            
            if response.status_code == 200:
                # 检查是否被限制
                html = response.text.lower()
                if any(kw in html for kw in ['video unavailable', 'private video', 'sign in']):
                    return False, "视频不可用或设为私密"
                return True, None
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, str(e)
    
    def _verify_bilibili(self, url: str) -> Tuple[bool, Optional[str]]:
        """验证B站资源可用性"""
        try:
            # 提取BVID
            bvid = None
            match = re.search(r'bilibili\.com/video/([^?/\s]+)', url)
            if match:
                bvid = match.group(1)
            
            if not bvid:
                return False, "无法解析B站BVID"
            
            # 检查视频状态
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ContentMonitor/1.5)',
                'Referer': 'https://www.bilibili.com'
            }
            
            api_url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
            response = httpx.get(api_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    return True, None
                else:
                    return False, data.get('message', '视频不可用')
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, str(e)
    
    def get_best_alternative(
        self, 
        alternatives: List[Dict],
        verify: bool = True
    ) -> Optional[Dict]:
        """选择最佳替代资源
        
        Args:
            alternatives: 替代资源列表
            verify: 是否验证资源可用性
            
        Returns:
            最佳替代资源，如果没有可用资源则返回None
        """
        if not alternatives:
            return None
        
        # 如果需要验证，先验证每个资源
        if verify:
            verified = []
            for alt in alternatives:
                platform = alt.get('platform', '')
                url = alt.get('url', '')
                
                if not url:
                    continue
                
                is_available, error = self.verify_source_available(url, platform)
                
                if is_available:
                    alt['verified'] = True
                    alt['verification_error'] = None
                    verified.append(alt)
                    logger.info(f"验证通过: {platform} - {url}")
                else:
                    logger.warning(f"验证失败: {platform} - {url} - {error}")
                    self._log_search_event({
                        "event": "verification_failed",
                        "url": url,
                        "platform": platform,
                        "error": error,
                        "timestamp": datetime.now().isoformat()
                    })
            
            alternatives = verified
        
        if not alternatives:
            return None
        
        # 按优先级和相关性排序
        alternatives.sort(
            key=lambda x: (
                x.get('priority', 999),
                -x.get('relevance', 0)
            )
        )
        
        best = alternatives[0]
        logger.info(f"选择最佳替代: {best.get('platform_name')} - {best.get('title', best.get('url', ''))}")
        
        self._log_search_event({
            "event": "best_alternative_selected",
            "selection": best,
            "total_candidates": len(alternatives),
            "timestamp": datetime.now().isoformat()
        })
        
        return best
    
    def get_download_url(self, resource: Dict) -> Optional[str]:
        """获取资源的下载URL（用于转录）
        
        Args:
            resource: 资源字典，包含 platform 和 url
            
        Returns:
            可下载的音频/视频URL
        """
        platform = resource.get('platform', '')
        url = resource.get('url', '')
        
        if platform == "youtube":
            return self._get_youtube_download_url(url)
        elif platform == "bilibili":
            return self._get_bilibili_download_url(url)
        else:
            # 其他平台返回原始URL
            return url
    
    def _get_youtube_download_url(self, url: str) -> str:
        """获取YouTube下载URL（用于yt-dlp）"""
        # yt-dlp 可以直接使用这个URL
        return url
    
    def _get_bilibili_download_url(self, url: str) -> str:
        """获取B站下载URL（用于yt-dlp）"""
        # yt-dlp 可以直接使用这个URL
        return url
    
    def _log_search_event(self, event: Dict) -> None:
        """记录搜索事件到日志"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.warning(f"写入搜索日志失败: {e}")
    
    def get_search_log(self, limit: int = 100) -> List[Dict]:
        """获取最近的搜索日志"""
        events = []
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        try:
                            events.append(json.loads(line))
                        except:
                            continue
        except Exception as e:
            logger.warning(f"读取搜索日志失败: {e}")
        
        return events
    
    def clear_cache(self) -> None:
        """清除搜索缓存"""
        self._search_cache.clear()
        logger.info("搜索缓存已清除")


class TranscribeWithFallback:
    """带Fallback的转录器封装"""
    
    def __init__(self, transcriber: 'WhisperTranscriber', config: Optional[Dict] = None):
        """初始化
        
        Args:
            transcriber: Whisper转录器实例
            config: 配置字典
        """
        self.transcriber = transcriber
        self.fallback_handler = FallbackHandler(config)
    
    def transcribe(
        self,
        audio_url: str,
        title: str,
        author: Optional[str] = None,
        source_platform: str = "unknown",
        **kwargs
    ) -> Dict:
        """带Fallback的转录
        
        Args:
            audio_url: 音频URL
            title: 内容标题
            author: 作者/播客名
            source_platform: 原始平台
            **kwargs: 其他参数传递给WhisperTranscriber
            
        Returns:
            转录结果字典
        """
        result = {
            'success': False,
            'source_platform': source_platform,
            'final_platform': source_platform,
            'fallback_used': False,
            'error': None,
            'transcription': None,
            'alternative_source': None,
        }
        
        # 尝试直接转录
        try:
            transcription = self.transcriber.transcribe_audio(audio_url, **kwargs)
            result['success'] = True
            result['transcription'] = transcription
            return result
            
        except Exception as e:
            result['error'] = str(e)
            
            # 检测是否为平台限制
            if not self.fallback_handler.detect_platform_restriction(e):
                # 非平台限制错误，直接返回失败
                logger.error(f"转录失败（非平台限制）: {e}")
                return result
            
            logger.warning(f"检测到平台限制，开始搜索替代资源...")
            result['fallback_used'] = True
        
        # 搜索替代资源
        alternatives = self.fallback_handler.search_alternative_sources(
            title=title,
            author=author,
            content_type='audio' if source_platform in ['xiaoyuzhou', 'apple_podcasts', 'spotify'] else 'video'
        )
        
        if not alternatives:
            logger.warning("未找到替代资源")
            return result
        
        # 选择最佳替代
        best = self.fallback_handler.get_best_alternative(alternatives, verify=True)
        
        if not best:
            logger.warning("没有可用的替代资源")
            return result
        
        result['alternative_source'] = best
        result['final_platform'] = best.get('platform', source_platform)
        
        # 使用替代资源转录
        try:
            download_url = self.fallback_handler.get_download_url(best)
            if download_url:
                logger.info(f"使用替代资源转录: {best.get('platform_name')} - {download_url}")
                transcription = self.transcriber.transcribe_audio(download_url, **kwargs)
                result['success'] = True
                result['transcription'] = transcription
                
                # 记录资源来源变更
                self._log_source_change(result)
                return result
                
        except Exception as e:
            logger.warning(f"替代资源转录失败: {e}")
            result['error'] = f"替代资源转录也失败: {e}"
        
        return result
    
    def _log_source_change(self, result: Dict) -> None:
        """记录资源来源变更"""
        change_event = {
            'event': 'source_change',
            'original_platform': result['source_platform'],
            'final_platform': result['final_platform'],
            'alternative': result.get('alternative_source', {}),
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            change_log = LOG_DIR / "source_changes.jsonl"
            with open(change_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(change_event, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.warning(f"记录来源变更失败: {e}")


# 命令行工具
def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='全网资源对比搜索')
    parser.add_argument('--title', '-t', required=True, help='内容标题')
    parser.add_argument('--author', '-a', help='作者/播客名')
    parser.add_argument('--type', default='audio', choices=['audio', 'video'], help='内容类型')
    parser.add_argument('--verify', '-v', action='store_true', help='验证资源可用性')
    parser.add_argument('--limit', '-l', type=int, default=10, help='最大结果数')
    
    args = parser.parse_args()
    
    # 初始化处理器
    handler = FallbackHandler()
    
    # 搜索
    print(f"🔍 搜索替代资源: {args.title}")
    if args.author:
        print(f"   作者: {args.author}")
    
    results = handler.search_alternative_sources(
        title=args.title,
        author=args.author,
        content_type=args.type
    )
    
    if not results:
        print("❌ 未找到替代资源")
        return
    
    print(f"\n📋 找到 {len(results)} 个替代资源:")
    for i, r in enumerate(results[:args.limit], 1):
        platform = r.get('platform_name', r.get('platform', ''))
        title = r.get('title', '')[:40]
        relevance = r.get('relevance', 0)
        verified = '✅' if r.get('verified') else '❓'
        print(f"  {i}. [{platform}] {verified} {title} (相关度: {relevance:.0%})")
        print(f"     URL: {r.get('url', '')}")
    
    # 选择最佳
    if args.verify:
        print("\n🔬 验证资源可用性...")
        best = handler.get_best_alternative(results, verify=True)
        if best:
            print(f"\n✅ 最佳替代: {best.get('platform_name')}")
            print(f"   {best.get('url', '')}")
        else:
            print("\n❌ 没有可用的替代资源")


if __name__ == '__main__':
    main()
