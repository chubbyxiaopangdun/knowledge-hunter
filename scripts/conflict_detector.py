#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冲突检测器 - 对比近期内容，发现观点冲突
维护观点库，检测不同来源的相反观点
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ViewPointConflict:
    """观点冲突数据类"""
    topic: str                      # 冲突主题
    viewpoint_a: str                # 观点A
    source_a: str                   # 来源A
    source_url_a: str               # 链接A
    viewpoint_b: str                # 观点B
    source_b: str                   # 来源B
    source_url_b: str               # 链接B
    conflict_level: str             # 冲突级别: strong/moderate/mild
    detected_at: str                # 检测时间


class ConflictDetector:
    """冲突检测器主类
    
    功能：
    1. 维护观点库（存储历史观点）
    2. 检测新观点与历史观点的冲突
    3. 生成"谁说了什么 vs 谁说了不同的"格式报告
    """
    
    # 冲突关键词定义
    CONFLICT_PATTERNS = {
        # A说是，B说否
        'contradiction': [
            ('会', '不会'), ('能', '不能'), ('应该', '不应该'),
            ('是', '不是'), ('有', '没有'), ('好', '不好'),
        ],
        # A说X，B说Y（数值/程度冲突）
        'numerical': [
            ('增长', '下降'), ('上升', '下跌'), ('多', '少'),
            ('大', '小'), ('快', '慢'), ('重要', '次要'),
        ],
        # A说X重要，B说Y重要（优先级冲突）
        'priority': [
            ('产品', '运营'), ('技术', '市场'), ('内容', '渠道'),
            ('用户', '收入'), ('增长', '利润'), ('短期', '长期'),
        ]
    }
    
    # 主题关键词映射
    TOPIC_KEYWORDS = {
        'AI是否会取代程序员': ['程序员', '开发者', 'coding', '写代码', '替代', '取代'],
        'AI对就业的影响': ['失业', '就业', '工作', '岗位', '裁员'],
        '创业方向选择': ['创业', '赛道', '方向', '机会', '风口'],
        '内容为王还是渠道为王': ['内容', '渠道', '流量', '分发'],
        '付费vs免费模式': ['付费', '免费', '订阅', '收费'],
        '全球化vs本土化': ['全球化', '出海', '本土化', '国际化'],
        'AI是否会取代程序员': ['程序员', '开发者', 'coding', '写代码', '替代', '取代'],
    }
    
    def __init__(self, viewpoint_db_path: Optional[str] = None):
        """初始化冲突检测器
        
        Args:
            viewpoint_db_path: 观点库路径
        """
        self.db_dir = Path(viewpoint_db_path) if viewpoint_db_path else Path(__file__).parent.parent / "数据" / "观点库"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        self.viewpoint_file = self.db_dir / "viewpoints.json"
        self.viewpoints = self._load_viewpoints()
    
    def _load_viewpoints(self) -> List[Dict]:
        """加载观点库"""
        if self.viewpoint_file.exists():
            try:
                with open(self.viewpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('viewpoints', [])
            except Exception as e:
                logger.error(f"观点库加载失败: {e}")
                return []
        return []
    
    def _save_viewpoints(self):
        """保存观点库"""
        data = {
            'updated_at': datetime.now().isoformat(),
            'viewpoints': self.viewpoints
        }
        
        with open(self.viewpoint_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_viewpoint(self, 
                      content: str, 
                      source: str, 
                      source_url: str = "",
                      category: str = "观点",
                      key_points: Optional[List[str]] = None):
        """添加观点到库
        
        Args:
            content: 观点内容摘要
            source: 来源名称
            source_url: 原文链接
            category: 内容类型
            key_points: 核心观点列表
        """
        viewpoint_entry = {
            'id': f"vp_{len(self.viewpoints) + 1}",
            'content': content,
            'source': source,
            'source_url': source_url,
            'category': category,
            'key_points': key_points or [],
            'added_at': datetime.now().isoformat(),
            'topics': self._extract_topics(content),
        }
        
        self.viewpoints.append(viewpoint_entry)
        self._save_viewpoints()
        
        logger.info(f"观点已添加: {source}")
    
    def _extract_topics(self, content: str) -> List[str]:
        """从内容中提取可能的主题"""
        topics = []
        content_lower = content.lower()
        
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in content_lower for kw in keywords):
                topics.append(topic)
        
        return topics
    
    def detect_conflicts(self, 
                        new_viewpoints: List[Dict],
                        days_range: int = 7) -> List[ViewPointConflict]:
        """检测冲突
        
        Args:
            new_viewpoints: 新观点列表
            days_range: 检测时间范围（天）
            
        Returns:
            List[ViewPointConflict]: 冲突列表
        """
        conflicts = []
        cutoff_date = datetime.now() - timedelta(days=days_range)
        
        # 获取近期历史观点
        historical = [
            vp for vp in self.viewpoints
            if datetime.fromisoformat(vp['added_at']) >= cutoff_date
        ]
        
        # 遍历新观点
        for new_vp in new_viewpoints:
            content = new_vp.get('content', '')
            source = new_vp.get('source', '未知')
            url = new_vp.get('source_url', '')
            
            # 与历史观点对比
            for old_vp in historical:
                if old_vp['source'] == source:
                    continue  # 跳过同来源
                
                conflict = self._check_conflict(
                    new_content=content,
                    new_source=source,
                    new_url=url,
                    old_content=old_vp['content'],
                    old_source=old_vp['source'],
                    old_url=old_vp.get('source_url', ''),
                )
                
                if conflict:
                    conflicts.append(conflict)
        
        return conflicts
    
    def _check_conflict(self,
                        new_content: str,
                        new_source: str,
                        new_url: str,
                        old_content: str,
                        old_source: str,
                        old_url: str) -> Optional[ViewPointConflict]:
        """检查两个观点是否冲突"""
        
        # 检查矛盾模式
        for pattern in self.CONFLICT_PATTERNS['contradiction']:
            word_a, word_b = pattern
            if (word_a in new_content and word_b in old_content) or \
               (word_b in new_content and word_a in old_content):
                return self._create_conflict(
                    topic=self._infer_topic(new_content, old_content),
                    viewpoint_a=new_content,
                    source_a=new_source,
                    url_a=new_url,
                    viewpoint_b=old_content,
                    source_b=old_source,
                    url_b=old_url,
                    level='strong'
                )
        
        # 检查数值冲突
        for pattern in self.CONFLICT_PATTERNS['numerical']:
            word_a, word_b = pattern
            if (word_a in new_content and word_b in old_content) or \
               (word_b in new_content and word_a in old_content):
                return self._create_conflict(
                    topic=self._infer_topic(new_content, old_content),
                    viewpoint_a=new_content,
                    source_a=new_source,
                    url_a=new_url,
                    viewpoint_b=old_content,
                    source_b=old_source,
                    url_b=old_url,
                    level='moderate'
                )
        
        # 检查优先级冲突
        for pattern in self.CONFLICT_PATTERNS['priority']:
            word_a, word_b = pattern
            if word_a in new_content and word_b in old_content:
                return self._create_conflict(
                    topic=self._infer_topic(new_content, old_content),
                    viewpoint_a=new_content,
                    source_a=new_source,
                    url_a=new_url,
                    viewpoint_b=old_content,
                    source_b=old_source,
                    url_b=old_url,
                    level='mild'
                )
        
        return None
    
    def _infer_topic(self, content_a: str, content_b: str) -> str:
        """推断冲突主题"""
        combined = content_a + content_b
        
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in combined.lower() for kw in keywords):
                return topic
        
        # 提取共同关键词作为主题
        words_a = set(content_a.lower().split()) & set(content_b.lower().split())
        if words_a:
            return ' '.join(list(words_a)[:3])
        
        return "观点冲突"
    
    def _create_conflict(self,
                         topic: str,
                         viewpoint_a: str, source_a: str, url_a: str,
                         viewpoint_b: str, source_b: str, url_b: str,
                         level: str) -> ViewPointConflict:
        """创建冲突对象"""
        return ViewPointConflict(
            topic=topic,
            viewpoint_a=viewpoint_a[:200] + '...' if len(viewpoint_a) > 200 else viewpoint_a,
            source_a=source_a,
            source_url_a=url_a,
            viewpoint_b=viewpoint_b[:200] + '...' if len(viewpoint_b) > 200 else viewpoint_b,
            source_b=source_b,
            source_url_b=url_b,
            conflict_level=level,
            detected_at=datetime.now().isoformat(),
        )
    
    def format_conflict_report(self, conflicts: List[ViewPointConflict]) -> str:
        """格式化冲突报告
        
        Args:
            conflicts: 冲突列表
            
        Returns:
            str: 格式化后的报告
        """
        if not conflicts:
            return "暂无观点冲突"
        
        lines = []
        lines.append("## 💡 观点冲突\n")
        
        level_emoji = {
            'strong': '🔴',
            'moderate': '🟡',
            'mild': '🟢'
        }
        
        for i, conflict in enumerate(conflicts, 1):
            emoji = level_emoji.get(conflict.conflict_level, '⚪')
            
            lines.append(f"**「{conflict.topic}」**\n")
            lines.append(f"{emoji} **{conflict.source_a}** 说：{conflict.viewpoint_a}")
            lines.append(f"{emoji} **{conflict.source_b}** 说：{conflict.viewpoint_b}")
            lines.append("你的看法呢？\n")
            lines.append("---")
            lines.append("")
        
        return '\n'.join(lines)
    
    def get_recent_viewpoints(self, days: int = 7) -> List[Dict]:
        """获取近期观点
        
        Args:
            days: 天数
            
        Returns:
            List[Dict]: 观点列表
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        return [
            vp for vp in self.viewpoints
            if datetime.fromisoformat(vp['added_at']) >= cutoff_date
        ]


# 测试代码
if __name__ == '__main__':
    detector = ConflictDetector()
    
    # 添加一些测试观点
    detector.add_viewpoint(
        content="AI 5年内会写90%的代码，程序员面临大规模失业",
        source="AI观察员",
        category="观点",
        key_points=["AI将取代大部分编程工作"]
    )
    
    detector.add_viewpoint(
        content="AI只是工具，创造力、架构能力无法替代",
        source="资深工程师",
        category="观点",
        key_points=["人类程序员有不可替代的价值"]
    )
    
    # 检测冲突
    new_vps = [
        {
            'content': '未来AI会取代程序员90%的工作",
            'source': '技术悲观派',
            'source_url': 'https://example.com/1'
        },
        {
            'content': 'AI永远无法真正替代程序员的创造性工作',
            'source': '技术乐观派',
            'source_url': 'https://example.com/2'
        }
    ]
    
    conflicts = detector.detect_conflicts(new_vps)
    
    report = detector.format_conflict_report(conflicts)
    print(report)
