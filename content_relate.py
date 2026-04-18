#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容关联器 - 追踪用户选题的相关内容更新
功能：
1. 维护用户的"历史选题库"（可配置）
2. 追踪用户选题的相关内容更新
3. 发现可以做"追踪/续集"的机会
4. 输出：你的选题有新更新
"""

import os
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

# 配置日志
LOG_DIR = Path(__file__).parent.parent / "日志"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / f"content_relate_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TopicUpdate:
    """选题更新类"""
    topic_id: str              # 选题ID
    user_topic: str            # 用户选题
    update_type: str           # 更新类型: new_content / update / opinion
    source_title: str          # 来源标题
    source_author: str         # 来源作者
    source_url: str            # 来源链接
    summary: str               # 更新摘要
    relevance_score: float     # 相关性分数
    suggested_angle: str       # 建议切入角度
    timestamp: str              # 发现时间


class ContentRelater:
    """内容关联器主类
    
    追踪用户选题的相关内容更新，帮助创作者发现追踪/续集机会
    """
    
    # 相关性关键词
    RELEVANCE_KEYWORDS = {
        # 通用
        '更新': ['更新', '后续', '续集', '新进展', '最新'],
        '观点': ['观点', '认为', '看法', '分析', '解读'],
        '案例': ['案例', '实战', '经验', '故事', '分享'],
        '数据': ['数据', '报告', '研究', '调查', '统计'],
    }
    
    # 追踪角度建议
    ANGLE_SUGGESTIONS = {
        'update': [
            '追踪视角：这个事件有了新进展',
            '对比视角：之前的判断对了吗？',
            '分析视角：新进展说明了什么？',
        ],
        'opinion': [
            '观点补充：这个角度你可能没想到',
            '反驳视角：作者说的有道理吗？',
            '延伸视角：这个问题还可以怎么看？',
        ],
        'case': [
            '案例补充：来看看真实案例',
            '经验分享：别人的实战经验',
            '避坑指南：这个坑要小心',
        ],
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化内容关联器
        
        Args:
            config: 配置字典
        """
        self.config = config or self._load_config()
        self.base_dir = Path(__file__).parent.parent
        
        # 选题库
        self.topic_library = self._load_topic_library()
        
        # 追踪记录
        self.tracking_file = self.base_dir / "选题库" / "追踪记录.json"
        self.tracking = self._load_tracking()
        
        # 关键词映射
        self.keyword_map = self._build_keyword_map()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        config_path = self.base_dir / "配置" / "选题配置.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"配置加载失败: {e}")
        
        return {
            'relevance_threshold': 0.5,   # 相关性阈值
            'max_updates': 5,              # 最大更新数
            'update_window_days': 7,       # 更新窗口（天）
        }
    
    def _load_topic_library(self) -> List[Dict]:
        """加载历史选题库
        
        Returns:
            选题列表
        """
        library_path = self.base_dir / "选题库" / "历史选题库.md"
        
        if not library_path.exists():
            logger.warning(f"选题库不存在: {library_path}")
            return []
        
        try:
            with open(library_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._parse_library(content)
        except Exception as e:
            logger.error(f"选题库加载失败: {e}")
            return []
    
    def _parse_library(self, content: str) -> List[Dict]:
        """解析选题库
        
        Args:
            content: Markdown内容
            
        Returns:
            选题列表
        """
        topics = []
        lines = content.split('\n')
        
        current_topic = None
        for line in lines:
            line = line.strip()
            
            # 跳过表头和分隔行
            if not line or line.startswith('|') and ('---' in line or '选题' in line):
                continue
            
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                
                # 解析选题行
                if len(parts) >= 2 and parts[1]:
                    topic = {
                        'title': parts[1],
                        'status': parts[2] if len(parts) > 2 else '',
                        'platform': parts[3] if len(parts) > 3 else '',
                        'notes': parts[4] if len(parts) > 4 else '',
                        'keywords': self._extract_keywords(parts[1]),
                    }
                    topics.append(topic)
        
        logger.info(f"加载 {len(topics)} 个历史选题")
        return topics
    
    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词
        
        Args:
            text: 文本内容
            
        Returns:
            关键词列表
        """
        keywords = []
        text_lower = text.lower()
        
        # 常见关键词
        common_kws = [
            'AI', 'ChatGPT', '人工智能', '大模型',
            '私域', '流量', '运营', '增长',
            '创业', '融资', '商业', '变现',
            '程序员', '开发', '产品', '运营',
            '小红书', '抖音', '自媒体', '博主',
            '职场', '裁员', '就业', '薪资',
            '投资', '股票', '房产', '理财',
        ]
        
        for kw in common_kws:
            if kw.lower() in text_lower:
                keywords.append(kw)
        
        return keywords
    
    def _load_tracking(self) -> Dict:
        """加载追踪记录
        
        Returns:
            追踪记录字典
        """
        if self.tracking_file.exists():
            try:
                with open(self.tracking_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"追踪记录加载失败: {e}")
        
        return {'tracked': {}, 'updates': []}
    
    def _save_tracking(self):
        """保存追踪记录"""
        try:
            with open(self.tracking_file, 'w', encoding='utf-8') as f:
                json.dump(self.tracking, f, ensure_ascii=False, indent=2)
            logger.info("追踪记录已保存")
        except Exception as e:
            logger.error(f"追踪记录保存失败: {e}")
    
    def _build_keyword_map(self) -> Dict[str, List[str]]:
        """构建关键词映射
        
        Returns:
            关键词映射字典
        """
        keyword_map = {}
        
        for topic in self.topic_library:
            for kw in topic.get('keywords', []):
                if kw not in keyword_map:
                    keyword_map[kw] = []
                keyword_map[kw].append(topic['title'])
        
        return keyword_map
    
    def find_updates(self, content_list: List[Dict]) -> List[TopicUpdate]:
        """发现内容更新
        
        Args:
            content_list: 内容列表
            
        Returns:
            选题更新列表
        """
        if not self.topic_library:
            logger.warning("选题库为空，跳过内容关联")
            return []
        
        updates = []
        window_days = self.config.get('update_window_days', 7)
        threshold = self.config.get('relevance_threshold', 0.5)
        
        for content in content_list:
            # 检查内容是否在窗口期内
            date_str = content.get('date', '') or content.get('published', '')
            if date_str:
                try:
                    content_date = datetime.strptime(date_str[:10], '%Y-%m-%d')
                    days_ago = (datetime.now() - content_date).days
                    if days_ago > window_days:
                        continue
                except:
                    pass
            
            # 计算与选题库的相关性
            title = content.get('title', '')
            description = content.get('description', '')
            viewpoint = content.get('viewpoint', '')
            text = f"{title} {description} {viewpoint}"
            
            relevance = self._calculate_relevance(text)
            
            if relevance >= threshold:
                update_type = self._classify_update(content, text)
                angle = self._suggest_angle(update_type)
                
                update = TopicUpdate(
                    topic_id=f"upd_{datetime.now().strftime('%Y%m%d%H%M')}",
                    user_topic=', '.join(relevance.get('matched_topics', [])[:2]),
                    update_type=update_type,
                    source_title=title,
                    source_author=content.get('author', '未知'),
                    source_url=content.get('url', ''),
                    summary=viewpoint[:100] + '...' if len(viewpoint) > 100 else viewpoint,
                    relevance_score=relevance.get('score', 0),
                    suggested_angle=angle,
                    timestamp=datetime.now().isoformat()
                )
                updates.append(update)
                
                # 更新追踪记录
                self._record_update(update)
        
        # 按相关性排序
        updates.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # 限制数量
        max_updates = self.config.get('max_updates', 5)
        updates = updates[:max_updates]
        
        logger.info(f"发现 {len(updates)} 条相关更新")
        return updates
    
    def _calculate_relevance(self, text: str) -> Dict:
        """计算相关性
        
        Args:
            text: 内容文本
            
        Returns:
            相关性结果 {'score': float, 'matched_topics': List[str]}
        """
        text_lower = text.lower()
        matched_topics = []
        match_count = 0
        
        for topic in self.topic_library:
            topic_title = topic.get('title', '').lower()
            topic_keywords = topic.get('keywords', [])
            
            # 标题匹配
            if any(kw.lower() in text_lower for kw in topic_keywords):
                matched_topics.append(topic['title'])
                match_count += 1
            
            # 关键词匹配
            for kw in topic_keywords:
                if kw.lower() in text_lower:
                    match_count += 0.5
                    if topic['title'] not in matched_topics:
                        matched_topics.append(topic['title'])
        
        # 计算相关性分数
        score = min(match_count / 3, 1.0)  # 归一化
        
        return {
            'score': round(score, 3),
            'matched_topics': matched_topics
        }
    
    def _classify_update(self, content: Dict, text: str) -> str:
        """分类更新类型
        
        Args:
            content: 内容字典
            text: 文本内容
            
        Returns:
            更新类型
        """
        text_lower = text.lower()
        
        # 检查关键词
        for update_type, keywords in self.RELEVANCE_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return update_type
        
        # 默认类型
        return 'opinion'
    
    def _suggest_angle(self, update_type: str) -> str:
        """建议切入角度
        
        Args:
            update_type: 更新类型
            
        Returns:
            角度建议
        """
        angles = self.ANGLE_SUGGESTIONS.get(update_type, self.ANGLE_SUGGESTIONS['opinion'])
        import random
        return random.choice(angles)
    
    def _record_update(self, update: TopicUpdate):
        """记录更新
        
        Args:
            update: 选题更新
        """
        update_dict = asdict(update)
        
        # 更新追踪记录
        update_id = update.topic_id
        self.tracking['tracked'][update_id] = update_dict
        self.tracking['updates'].append({
            'update_id': update_id,
            'user_topic': update.user_topic,
            'timestamp': update.timestamp,
        })
        
        # 保留最近100条记录
        self.tracking['updates'] = self.tracking['updates'][-100:]
        
        self._save_tracking()
    
    def get_followup_suggestions(self, updates: List[TopicUpdate]) -> List[Dict]:
        """获取追踪/续集建议
        
        Args:
            updates: 选题更新列表
            
        Returns:
            续集建议列表
        """
        suggestions = []
        
        for update in updates:
            # 基于更新生成续集建议
            suggestion = {
                'original_topic': update.user_topic,
                'new_update': update.source_title,
                'suggested_title': self._generate_followup_title(update),
                'angle': update.suggested_angle,
                'content_type': self._suggest_content_type(update.update_type),
            }
            suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_followup_title(self, update: TopicUpdate) -> str:
        """生成续集标题
        
        Args:
            update: 选题更新
            
        Returns:
            续集标题
        """
        import random
        templates = [
            "{topic}一年后，我发现了这些新变化",
            "追踪「{topic}」：最新进展来了",
            "关于「{topic}」，又有新消息了",
            "{topic}后续：事实检验时间",
        ]
        
        template = random.choice(templates)
        return template.format(topic=update.user_topic[:10])
    
    def _suggest_content_type(self, update_type: str) -> str:
        """建议内容类型
        
        Args:
            update_type: 更新类型
            
        Returns:
            内容类型
        """
        type_map = {
            'update': '追踪报道',
            'opinion': '观点补充',
            'case': '案例分享',
            'data': '数据解读',
        }
        return type_map.get(update_type, '观点分享')
    
    def format_updates(self, updates: List[TopicUpdate]) -> str:
        """格式化更新内容
        
        Args:
            updates: 选题更新列表
            
        Returns:
            格式化文本
        """
        if not updates:
            return "📌 你的选题暂无更新"
        
        lines = []
        lines.append("📌 你的选题有更新（可追踪）\n━━━━━━━━━━━━━━━━━━━\n")
        
        for update in updates:
            # 类型emoji
            type_emoji = {
                'update': '🔄',
                'opinion': '💭',
                'case': '📊',
                'data': '📈',
            }.get(update.update_type, '📌')
            
            lines.append(f"你之前做过「{update.user_topic}」")
            lines.append(f"→ 本周相关更新：")
            lines.append(f"  {type_emoji} {update.source_title}")
            lines.append(f"  by {update.source_author}")
            if update.source_url:
                lines.append(f"  🔗 {update.source_url}")
            lines.append(f"  💡 建议角度：{update.suggested_angle}")
            lines.append("")
        
        return "\n".join(lines)
    
    def add_topic(self, title: str, status: str = '待创作', platform: str = '', notes: str = ''):
        """添加选题到库
        
        Args:
            title: 选题标题
            status: 状态
            platform: 平台
            notes: 备注
        """
        # 解析Markdown
        library_path = self.base_dir / "选题库" / "历史选题库.md"
        
        keywords = self._extract_keywords(title)
        
        # 添加新行
        new_row = f"| {datetime.now().strftime('%Y-%m-%d')} | {title} | {status} | {platform} | {notes} |"
        
        try:
            with open(library_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{new_row}\n")
            
            # 更新内存中的选题库
            self.topic_library.append({
                'title': title,
                'status': status,
                'platform': platform,
                'notes': notes,
                'keywords': keywords,
            })
            
            # 重建关键词映射
            self.keyword_map = self._build_keyword_map()
            
            logger.info(f"选题已添加: {title}")
        except Exception as e:
            logger.error(f"选题添加失败: {e}")


def main():
    """测试函数"""
    relater = ContentRelater()
    
    # 模拟内容列表
    content_list = [
        {
            'title': 'AI创业的3个机会',
            'author': '张三',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'viewpoint': 'AI创业机会很多，但要注意差异化竞争...',
            'url': 'https://example.com/ai-startup',
        },
        {
            'title': '私域流量运营一年后的真实感受',
            'author': '李四',
            'date': (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')),
            'viewpoint': '私域运营一年后，我发现...',
            'url': 'https://example.com/siyu-experience',
        },
    ]
    
    from datetime import timedelta
    
    # 发现更新
    updates = relater.find_updates(content_list)
    
    print("\n" + "="*50)
    print("内容关联结果")
    print("="*50)
    print(relater.format_updates(updates))


if __name__ == '__main__':
    main()
