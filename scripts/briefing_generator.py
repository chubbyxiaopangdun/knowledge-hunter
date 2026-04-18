#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简报生成器 - 组装每日简报
将观点、评分、冲突等内容组装成统一格式
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BriefingData:
    """简报数据类"""
    date: str                           # 日期
    videos: List[Dict]                  # 视频内容
    podcasts: List[Dict]                # 播客内容
    conflicts: List[Dict]               # 观点冲突
    statistics: Dict                    # 统计数据
    generated_at: str                   # 生成时间


class BriefingGenerator:
    """简报生成器主类
    
    功能：
    1. 组装每日简报格式
    2. 支持自定义模板
    3. 生成飞书可用的Markdown格式
    """
    
    # 平台类型映射
    PLATFORM_TYPES = {
        'youtube': '视频',
        'bilibili': '视频',
        'xiaoyuzhou': '播客',
        'podcast': '播客',
        'twitter': '资讯',
    }
    
    def __init__(self, template_path: Optional[str] = None):
        """初始化简报生成器
        
        Args:
            template_path: 模板文件路径
        """
        self.template_dir = Path(__file__).parent.parent / "templates"
        self.template_path = template_path or self.template_dir / "每日简报模板.md"
        self.template = self._load_template()
        
        self.output_dir = Path(__file__).parent.parent / "输出" / "简报"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_template(self) -> str:
        """加载模板"""
        if Path(self.template_path).exists():
            with open(self.template_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # 默认模板
        return self._get_default_template()
    
    def _get_default_template(self) -> str:
        """获取默认模板"""
        return """📰 今日内容简报 | {date}

> 自动化生成 | 知识猎手 v1.1.0

---

## 🎬 值得看的视频（{video_count}个）

{video_content}

---

## 🎧 值得听的播客（{podcast_count}个）

{podcast_content}

---

## 💡 观点冲突

{conflict_content}

---

## 📊 今日统计

- 监控内容源：{source_count} 个
- 新增内容：{new_count} 个
- 平均评分：{avg_score} 分
- 简报生成时间：{generate_time}

---

*本简报由「知识猎手」自动生成*
*如有质量问题，可回复反馈*
"""
    
    def generate(self, 
                 date: Optional[str] = None,
                 videos: Optional[List[Dict]] = None,
                 podcasts: Optional[List[Dict]] = None,
                 conflicts: Optional[List[Dict]] = None,
                 scores: Optional[List[Dict]] = None) -> str:
        """生成简报
        
        Args:
            date: 日期，默认为今天
            videos: 视频内容列表
            podcasts: 播客内容列表
            conflicts: 观点冲突列表
            scores: 评分结果列表
            
        Returns:
            str: 格式化简报
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        videos = videos or []
        podcasts = podcasts or []
        conflicts = conflicts or []
        scores = scores or []
        
        logger.info(f"开始生成简报: {date}")
        
        # 计算统计数据
        statistics = self._calculate_statistics(videos, podcasts, scores)
        
        # 格式化各部分内容
        video_content = self._format_videos(videos)
        podcast_content = self._format_podcasts(podcasts)
        conflict_content = self._format_conflicts(conflicts)
        
        # 填充模板
        briefing = self.template.format(
            date=date,
            video_count=len(videos),
            podcast_count=len(podcasts),
            video_content=video_content,
            podcast_content=podcast_content,
            conflict_content=conflict_content,
            source_count=statistics['source_count'],
            new_count=statistics['new_count'],
            avg_score=statistics['avg_score'],
            generate_time=datetime.now().strftime('%H:%M:%S'),
        )
        
        logger.info(f"简报生成完成: {len(briefing)} 字符")
        
        return briefing
    
    def _calculate_statistics(self, 
                              videos: List[Dict], 
                              podcasts: List[Dict],
                              scores: List[Dict]) -> Dict:
        """计算统计数据"""
        all_contents = videos + podcasts
        
        # 统计来源数
        sources = set()
        for c in all_contents:
            if 'source' in c:
                sources.add(c['source'])
            if 'author' in c:
                sources.add(c['author'])
        
        # 计算平均分
        total_score = sum(s.get('score', 0) for s in scores)
        avg_score = total_score / len(scores) if scores else 0
        
        return {
            'source_count': len(sources),
            'new_count': len(all_contents),
            'avg_score': round(avg_score, 1),
        }
    
    def _format_videos(self, videos: List[Dict]) -> str:
        """格式化视频内容"""
        if not videos:
            return "_暂无视频内容_"
        
        lines = []
        
        for i, video in enumerate(videos, 1):
            title = video.get('title', '未知标题')
            author = video.get('author', video.get('source', '未知作者'))
            url = video.get('url', video.get('source_url', ''))
            score = video.get('score', 0)
            recommendation = video.get('recommendation', '')
            category = video.get('category', '观点')
            viewpoint = video.get('viewpoint', video.get('key_points', []))
            
            # 核心观点
            core_viewpoint = ""
            if isinstance(viewpoint, list) and viewpoint:
                core_viewpoint = viewpoint[0] if len(viewpoint) > 0 else ""
            elif isinstance(viewpoint, str):
                core_viewpoint = viewpoint
            
            lines.append(f"{i}️⃣ **{title}** by {author}")
            
            if core_viewpoint:
                lines.append(f"   核心观点：{core_viewpoint[:100]}...")
            
            if recommendation:
                lines.append(f"   推荐：{recommendation}")
            
            if url:
                lines.append(f"   🔗 {url}")
            
            lines.append("")
        
        return '\n'.join(lines)
    
    def _format_podcasts(self, podcasts: List[Dict]) -> str:
        """格式化播客内容"""
        if not podcasts:
            return "_暂无播客内容_"
        
        lines = []
        
        for i, podcast in enumerate(podcasts, 1):
            title = podcast.get('title', '未知标题')
            author = podcast.get('author', podcast.get('source', '未知主播'))
            url = podcast.get('url', podcast.get('source_url', ''))
            duration = podcast.get('duration', podcast.get('duration_text', ''))
            recommendation = podcast.get('recommendation', '')
            viewpoint = podcast.get('viewpoint', podcast.get('key_points', []))
            
            # 适合场景
            scenario = f"适合场景：{duration}" if duration else "适合场景：通勤路上"
            
            # 核心观点
            core_viewpoint = ""
            if isinstance(viewpoint, list) and viewpoint:
                core_viewpoint = viewpoint[0] if len(viewpoint) > 0 else ""
            elif isinstance(viewpoint, str):
                core_viewpoint = viewpoint
            
            lines.append(f"{i}️⃣ **{title}** by {author}")
            
            if core_viewpoint:
                lines.append(f"   核心观点：{core_viewpoint[:100]}...")
            
            lines.append(f"   {scenario}")
            
            if recommendation:
                lines.append(f"   推荐：{recommendation}")
            
            lines.append("")
        
        return '\n'.join(lines)
    
    def _format_conflicts(self, conflicts: List[Dict]) -> str:
        """格式化观点冲突"""
        if not conflicts:
            return "_暂无观点冲突_"
        
        lines = []
        
        level_emoji = {
            'strong': '🔴',
            'moderate': '🟡',
            'mild': '🟢'
        }
        
        for conflict in conflicts[:3]:  # 最多显示3个冲突
            topic = conflict.get('topic', '观点冲突')
            viewpoint_a = conflict.get('viewpoint_a', '')
            source_a = conflict.get('source_a', '来源A')
            viewpoint_b = conflict.get('viewpoint_b', '')
            source_b = conflict.get('source_b', '来源B')
            level = conflict.get('conflict_level', 'moderate')
            
            emoji = level_emoji.get(level, '⚪')
            
            lines.append(f"**「{topic}」**\n")
            lines.append(f"{emoji} **{source_a}** 说：{viewpoint_a[:80]}...")
            lines.append(f"{emoji} **{source_b}** 说：{viewpoint_b[:80]}...")
            lines.append("你的看法呢？\n")
        
        return '\n'.join(lines)
    
    def save(self, briefing: str, date: Optional[str] = None) -> str:
        """保存简报
        
        Args:
            briefing: 简报内容
            date: 日期
            
        Returns:
            str: 保存的文件路径
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        output_file = self.output_dir / f"简报_{date}.md"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(briefing)
        
        logger.info(f"简报已保存: {output_file}")
        
        return str(output_file)
    
    def save_json(self, 
                  data: BriefingData, 
                  date: Optional[str] = None) -> str:
        """保存简报数据（JSON格式）
        
        Args:
            data: 简报数据
            date: 日期
            
        Returns:
            str: 保存的文件路径
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        output_file = self.output_dir / f"简报数据_{date}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(data), f, ensure_ascii=False, indent=2)
        
        logger.info(f"简报数据已保存: {output_file}")
        
        return str(output_file)
    
    def generate_and_save(self,
                          date: Optional[str] = None,
                          videos: Optional[List[Dict]] = None,
                          podcasts: Optional[List[Dict]] = None,
                          conflicts: Optional[List[Dict]] = None,
                          scores: Optional[List[Dict]] = None) -> Tuple[str, BriefingData]:
        """生成并保存简报
        
        Args:
            date: 日期
            videos: 视频内容
            podcasts: 播客内容
            conflicts: 观点冲突
            scores: 评分结果
            
        Returns:
            Tuple[str, BriefingData]: (Markdown简报, 简报数据)
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # 生成Markdown
        briefing = self.generate(
            date=date,
            videos=videos,
            podcasts=podcasts,
            conflicts=conflicts,
            scores=scores
        )
        
        # 构建数据对象
        statistics = self._calculate_statistics(videos or [], podcasts or [], scores or [])
        
        data = BriefingData(
            date=date,
            videos=videos or [],
            podcasts=podcasts or [],
            conflicts=conflicts or [],
            statistics=statistics,
            generated_at=datetime.now().isoformat(),
        )
        
        # 保存
        self.save(briefing, date)
        self.save_json(data, date)
        
        return briefing, data


# 测试代码
if __name__ == '__main__':
    generator = BriefingGenerator()
    
    # 模拟数据
    videos = [
        {
            'title': 'AI时代的创业机会',
            'author': '张三',
            'url': 'https://youtube.com/watch?v=xxx',
            'score': 8.5,
            'recommendation': '⭐⭐⭐⭐⭐ 强烈推荐！对未来趋势的深度洞察',
            'viewpoint': ['未来3年AI Agent将成为创业新赛道'],
        }
    ]
    
    podcasts = [
        {
            'title': '对话李四：互联网下半场',
            'author': '李四',
            'url': 'https://xiaoyuzhoufm.com/episode/xxx',
            'duration': '30分钟',
            'viewpoint': ['流量红利见顶，用户价值才是护城河'],
        }
    ]
    
    conflicts = [
        {
            'topic': 'AI是否会取代程序员',
            'viewpoint_a': 'AI 5年内会写90%的代码',
            'source_a': '张三',
            'viewpoint_b': 'AI只是工具，创造力无法替代',
            'source_b': '李四',
            'conflict_level': 'strong',
        }
    ]
    
    # 生成简报
    briefing = generator.generate(
        date='2026-04-18',
        videos=videos,
        podcasts=podcasts,
        conflicts=conflicts,
        scores=[{'score': 8.5}]
    )
    
    print(briefing)
