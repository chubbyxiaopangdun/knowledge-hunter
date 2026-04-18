#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twitter/X监控模块
获取用户推文文本内容
"""

import os
import re
import json
import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TwitterMonitor:
    """Twitter/X监控器"""
    
    def __init__(self, config_path: str = "./内容监控/配置/博主列表.md"):
        self.config_path = config_path
        self.output_dir = "./内容监控/输出/Twitter"
        self.state_file = "./内容监控/log/Twitter状态.json"
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
    
    def parse_twitter_list(self) -> List[Dict]:
        """从配置文件解析Twitter账号列表"""
        accounts = []
        current_section = None
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('## Twitter'):
                    current_section = 'twitter'
                elif line.startswith('##') or line.startswith('---'):
                    current_section = None
                elif current_section == 'twitter' and '|' in line and '用户' in line:
                    continue
                elif current_section == 'twitter' and '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 3:
                        username = self._extract_username(parts[2])
                        if username:
                            accounts.append({
                                'name': parts[1],
                                'username': username,
                                'note': parts[3] if len(parts) > 3 else ''
                            })
        
        return accounts
    
    def _extract_username(self, text: str) -> Optional[str]:
        """提取用户名"""
        text = text.strip().lstrip('@')
        
        # 已经是纯用户名
        if text and not text.startswith('http'):
            return text
        
        # 从URL提取
        patterns = [
            r'twitter\.com/([a-zA-Z0-9_]+)',
            r'x\.com/([a-zA-Z0-9_]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def fetch_tweets(self, username: str) -> List[Dict]:
        """获取用户推文"""
        # 使用nitter.net作为推特的前端（无需登录）
        # 备选： syndication API
        
        # 方法1: syndication.twitter.com
        url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ContentMonitor/1.0)',
            'Accept': 'application/json',
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    tweets = data.get('body', {}).get('timeline', {}).get('items', [])
                    
                    return [{
                        'id': tweet.get('tweet', {}).get('id_str'),
                        'text': tweet.get('tweet', {}).get('full_text', ''),
                        'created_at': tweet.get('tweet', {}).get('created_at', ''),
                        'link': f"https://twitter.com/{username}/status/{tweet.get('tweet', {}).get('id_str')}",
                        'username': username,
                    } for tweet in tweets[:20]]  # 最多获取20条
                
        except Exception as e:
            logger.warning(f"syndication API失败: {e}")
        
        # 方法2: 使用Nitter实例
        nitter_instances = [
            'nitter.net',
            'nitter.privacydev.net',
            'xcancel.com',
        ]
        
        for instance in nitter_instances:
            try:
                url = f"https://{instance}/{username}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (compatible; ContentMonitor/1.0)',
                }
                
                with httpx.Client() as client:
                    response = client.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        return self._parse_nitter_html(response.text, username)
                        
            except Exception as e:
                logger.warning(f"Nitter {instance} 失败: {e}")
                continue
        
        logger.error(f"无法获取 {username} 的推文")
        return []
    
    def _parse_nitter_html(self, html: str, username: str) -> List[Dict]:
        """解析Nitter HTML获取推文"""
        tweets = []
        
        # 简单的HTML解析
        tweet_pattern = r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>'
        time_pattern = r'<span class="tweet-date[^"]*"[^>]*>.*?<a href="([^"]+)">(.*?)</a>'
        
        matches = re.finditer(tweet_pattern, html, re.DOTALL)
        time_matches = list(re.finditer(time_pattern, html, re.DOTALL))
        
        for i, match in enumerate(matches):
            text = match.group(1)
            # 清理HTML标签
            text = re.sub(r'<[^>]+>', '', text)
            text = self._clean_text(text)
            
            if text and len(text) > 10:  # 过滤太短的推文
                link = ""
                timestamp = ""
                
                if i < len(time_matches):
                    link = time_matches[i].group(1)
                    timestamp = time_matches[i].group(2)
                
                tweets.append({
                    'id': f"{username}_{i}",
                    'text': text,
                    'created_at': timestamp,
                    'link': f"https://twitter.com{link}" if link.startswith('/') else link,
                    'username': username,
                })
        
        return tweets[:10]
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def check_updates(self, username: str) -> List[Dict]:
        """检查新推文"""
        all_tweets = self.fetch_tweets(username)
        updates = []
        
        for tweet in all_tweets:
            tweet_id = tweet.get('id', '')
            if tweet_id and tweet_id not in self.processed:
                updates.append(tweet)
        
        return updates
    
    def save_tweets(self, tweets: List[Dict], username: str) -> List[str]:
        """保存推文"""
        if not tweets:
            return []
        
        # 按日期分组
        tweets_by_date = {}
        for tweet in tweets:
            date = tweet.get('created_at', '')[:10]
            if date not in tweets_by_date:
                tweets_by_date[date] = []
            tweets_by_date[date].append(tweet)
        
        filepaths = []
        
        for date, day_tweets in tweets_by_date.items():
            content = self._generate_markdown(day_tweets, username, date)
            filename = f"@{username}_{date}.md"
            filepath = Path(self.output_dir) / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            filepaths.append(str(filepath))
            logger.info(f"保存完成: {filepath}")
        
        return filepaths
    
    def _generate_markdown(self, tweets: List[Dict], username: str, date: str) -> str:
        """生成Markdown格式"""
        lines = []
        lines.append(f"# @{username} 推文汇总\n")
        lines.append(f"> 日期: {date}\n")
        lines.append(f"> 抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("\n---\n\n")
        
        for i, tweet in enumerate(tweets, 1):
            lines.append(f"## 推文 {i}\n\n")
            lines.append(f"{tweet['text']}\n\n")
            lines.append(f"- 发布时间: {tweet['created_at']}\n")
            lines.append(f"- 链接: {tweet['link']}\n")
            lines.append("\n---\n\n")
        
        return ''.join(lines)
    
    def run(self) -> List[str]:
        """执行监控任务"""
        accounts = self.parse_twitter_list()
        logger.info(f"找到 {len(accounts)} 个Twitter账号订阅")
        
        all_filepaths = []
        
        for account in accounts:
            username = account['username']
            logger.info(f"检查账号: {account['name']} (@{username})")
            
            updates = self.check_updates(username)
            
            if not updates:
                logger.info(f"  无新推文")
                continue
            
            logger.info(f"  发现 {len(updates)} 条新推文")
            
            # 保存推文
            filepaths = self.save_tweets(updates, username)
            all_filepaths.extend(filepaths)
            
            # 更新状态
            for tweet in updates:
                tweet_id = tweet.get('id', '')
                if tweet_id:
                    self.processed[tweet_id] = {
                        'text': tweet['text'][:100],  # 保存前100字
                        'saved_at': datetime.now().isoformat(),
                    }
            
            self._save_state()
        
        return all_filepaths


if __name__ == "__main__":
    monitor = TwitterMonitor()
    results = monitor.run()
    print(f"\n处理完成，共保存 {len(results)} 个文件")
