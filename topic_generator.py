#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选题生成器 - 基于热点话题和观点对比生成选题建议
功能：
1. 基于热点话题生成选题建议
2. 基于观点对比生成选题建议
3. 生成角度建议（可以从哪个方向切入）
4. 输出：具体选题标题+切入角度
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
        logging.FileHandler(LOG_DIR / f"topic_generator_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TopicSuggestion:
    """选题建议类"""
    topic_id: str              # 选题ID
    title: str                 # 选题标题
    angle: str                 # 切入角度
    source_topic: str          # 来源话题
    source_type: str          # 来源类型: hot_topic / viewpoint_conflict
    key_points: List[str]      # 关键要点
    recommended_format: str    # 推荐格式: 观点/测评/教程/故事
    target_audience: str       # 目标受众
    difficulty: str            # 难度: easy / medium / hard
    estimated_read_time: int   # 预计阅读时间(分钟)
    timestamp: str             # 生成时间


class TopicGenerator:
    """选题生成器主类
    
    基于热点话题和观点对比生成有价值的选题建议
    """
    
    # 选题模板
    TITLE_TEMPLATES = {
        'warning': [
            '{topic}的{num}个陷阱，踩中一个就死',
            '做{topic}之前，先想清楚这{num}点',
            '{topic}失败的{num}个原因，第{num}个最致命',
        ],
        'truth': [
            '{topic}的真相，第{num}个你一定不知道',
            '关于{topic}，我发现的{num}个真相',
            '{topic}一年后，我后悔了{num}件事',
        ],
        'debate': [
            '{topic}A还是B？看完就有答案',
            '关于{topic}，大佬们吵翻了',
            '{topic}，我站{side}',
        ],
        'guide': [
            '{topic}入门指南，看这一篇就够了',
            '{topic}完整教程，从小白到精通',
            '{topic}实操手册，收藏这一篇',
        ],
        'story': [
            '我做{topic}的第{time}天，看到了这些',
            '{topic}一年后的真实感受',
            '从{topic}失败到成功的全过程',
        ],
    }
    
    # 内容格式
    CONTENT_FORMATS = {
        '观点': ['争议话题', '观点表达', '对比分析'],
        '测评': ['产品测评', '工具对比', '横评体验'],
        '教程': ['入门指南', '进阶技巧', '实战案例'],
        '故事': ['个人经历', '访谈记录', '案例复盘'],
    }
    
    # 平台适配
    PLATFORM_STYLES = {
        'wechat': '深度长文，有深度有思考',
        'xiaohongshu': '轻松有趣，有干货有情绪',
        'bilibili': '视频脚本，有梗有料',
        'douyin': '短平快，30秒抓住眼球',
        'zhihu': '专业分析，有理有据',
    }
    
    def __init__(self, llm_config: Optional[Dict] = None, config: Optional[Dict] = None):
        """初始化选题生成器
        
        Args:
            llm_config: LLM配置
            config: 生成器配置
        """
        self.llm_config = llm_config or self._load_llm_config()
        self.config = config or self._load_config()
        self.base_dir = Path(__file__).parent.parent
        self.output_dir = self.base_dir / "输出" / "选题建议"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 选题库（历史选题）
        self.topic_db = self._load_topic_db()
    
    def _load_llm_config(self) -> Dict:
        """加载LLM配置"""
        config_path = self.base_dir / "配置" / "LLM配置.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"LLM配置加载失败: {e}")
        
        return {
            'provider': 'coze',
            'model': 'gpt-4o-mini',
            'temperature': 0.8,
        }
    
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
            'default_platform': 'xiaohongshu',
            'suggestion_count': 5,
            'use_llm': False,  # 是否使用LLM生成
        }
    
    def _load_topic_db(self) -> List[Dict]:
        """加载历史选题库"""
        db_path = self.base_dir / "选题库" / "历史选题库.md"
        if db_path.exists():
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 解析Markdown表格
                    return self._parse_topic_db(content)
            except Exception as e:
                logger.warning(f"选题库加载失败: {e}")
        return []
    
    def _parse_topic_db(self, content: str) -> List[Dict]:
        """解析历史选题库
        
        Args:
            content: Markdown内容
            
        Returns:
            选题列表
        """
        topics = []
        lines = content.split('\n')
        
        for line in lines:
            if '|' in line and not line.startswith('|') and not line.startswith('-'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    topics.append({
                        'title': parts[1],
                        'status': parts[2] if len(parts) > 2 else '',
                        'platform': parts[3] if len(parts) > 3 else '',
                        'notes': parts[4] if len(parts) > 4 else '',
                    })
        
        return topics
    
    def generate_from_hot_topics(self, hot_topics: List[Dict]) -> List[TopicSuggestion]:
        """基于热点话题生成选题建议
        
        Args:
            hot_topics: 热点话题列表
            
        Returns:
            选题建议列表
        """
        suggestions = []
        
        for topic in hot_topics[:5]:  # 最多5个话题
            topic_name = topic.get('topic_name', '')
            keywords = topic.get('keywords', [])
            sources = topic.get('sources', [])
            
            if not topic_name:
                continue
            
            # 生成多个选题
            titles = self._generate_titles(topic_name, keywords)
            
            for i, title in enumerate(titles):
                suggestion = TopicSuggestion(
                    topic_id=f"ht_{datetime.now().strftime('%Y%m%d')}_{i}",
                    title=title,
                    angle=self._generate_angle(topic_name),
                    source_topic=topic_name,
                    source_type='hot_topic',
                    key_points=self._extract_key_points(topic),
                    recommended_format=self._suggest_format(topic_name),
                    target_audience=self._suggest_audience(topic_name),
                    difficulty='medium',
                    estimated_read_time=5,
                    timestamp=datetime.now().isoformat()
                )
                suggestions.append(suggestion)
        
        logger.info(f"基于热点话题生成 {len(suggestions)} 个选题建议")
        return suggestions
    
    def generate_from_conflicts(self, conflicts: List[Dict]) -> List[TopicSuggestion]:
        """基于观点对比生成选题建议
        
        Args:
            conflicts: 观点冲突列表
            
        Returns:
            选题建议列表
        """
        suggestions = []
        
        for i, conflict in enumerate(conflicts[:3]):  # 最多3个冲突
            topic = conflict.get('topic', '')
            viewpoint_a = conflict.get('viewpoint_a', {})
            viewpoint_b = conflict.get('viewpoint_b', {})
            
            if not topic:
                continue
            
            # 生成对比类选题
            title = f"关于「{topic}」，大佬们吵翻了，真相是..."
            
            suggestion = TopicSuggestion(
                topic_id=f"cf_{datetime.now().strftime('%Y%m%d')}_{i}",
                title=title,
                angle='对比视角：整理双方观点，给出自己的判断',
                source_topic=topic,
                source_type='viewpoint_conflict',
                key_points=[
                    f"🔴 {viewpoint_a.get('author', 'A')}说：{viewpoint_a.get('viewpoint', '')}",
                    f"🔵 {viewpoint_b.get('author', 'B')}说：{viewpoint_b.get('viewpoint', '')}",
                ],
                recommended_format='观点',
                target_audience='职场人/创业者',
                difficulty='medium',
                estimated_read_time=8,
                timestamp=datetime.now().isoformat()
            )
            suggestions.append(suggestion)
        
        logger.info(f"基于观点对比生成 {len(suggestions)} 个选题建议")
        return suggestions
    
    def _generate_titles(self, topic: str, keywords: List[str]) -> List[str]:
        """生成选题标题
        
        Args:
            topic: 话题名称
            keywords: 关键词列表
            
        Returns:
            标题列表
        """
        titles = []
        
        # 使用模板生成
        import random
        random.seed(hash(topic))
        
        template_cats = ['warning', 'truth', 'debate']
        for cat in template_cats:
            templates = self.TITLE_TEMPLATES.get(cat, [])
            if templates:
                template = random.choice(templates)
                num = random.randint(3, 5)
                time_map = {30: '30天', 90: '3个月', 365: '一年'}
                time_key = random.choice(list(time_map.keys()))
                time_str = time_map[time_key]
                
                # 替换占位符
                title = template
                title = title.replace('{topic}', topic)
                title = title.replace('{num}', str(num))
                title = title.replace('{time}', time_str)
                title = title.replace('{side}', random.choice(['A', 'B', '中间路线']))
                
                titles.append(title)
        
        # 如果关键词足够，生成一个精准选题
        if keywords:
            kw = keywords[0] if keywords else topic
            titles.append(f"「{kw}」为什么突然火了？我来分析一下")
        
        return titles[:3]  # 最多3个标题
    
    def _generate_angle(self, topic: str) -> str:
        """生成切入角度
        
        Args:
            topic: 话题名称
            
        Returns:
            切入角度描述
        """
        angles = {
            'AI创业': '从创业者和投资人的双重视角，分析AI赛道的机与危',
            '私域流量': '从实操经验出发，告诉你私域运营的真实面貌',
            '程序员危机': '从程序员转型案例出发，给出具体可操作的建议',
            '流量获取': '拆解成功案例，总结可复用的流量获取方法论',
            '职场变化': '从真实故事出发，引发职场人的共鸣和思考',
            '自媒体变现': '给出具体的变现路径和方法，不画饼',
        }
        
        return angles.get(topic, f'从{topic}切入，给出有价值的观点和建议')
    
    def _extract_key_points(self, topic: Dict) -> List[str]:
        """提取关键要点
        
        Args:
            topic: 话题信息
            
        Returns:
            关键要点列表
        """
        points = []
        
        # 从相关内容中提取
        contents = topic.get('related_content', [])
        for c in contents[:2]:
            viewpoint = c.get('viewpoint', '')
            if viewpoint:
                # 取前50字
                point = viewpoint[:50] + '...' if len(viewpoint) > 50 else viewpoint
                points.append(point)
        
        return points or ['需要进一步分析']
    
    def _suggest_format(self, topic: str) -> str:
        """建议内容格式
        
        Args:
            topic: 话题名称
            
        Returns:
            建议格式
        """
        format_map = {
            'AI创业': '观点',
            '私域流量': '教程',
            '程序员危机': '故事',
            '流量获取': '教程',
            '职场变化': '观点',
            '自媒体变现': '教程',
        }
        
        return format_map.get(topic, '观点')
    
    def _suggest_audience(self, topic: str) -> str:
        """建议目标受众
        
        Args:
            topic: 话题名称
            
        Returns:
            目标受众描述
        """
        audience_map = {
            'AI创业': '创业者/投资人/互联网从业者',
            '私域流量': '运营人/电商从业者/中小企业主',
            '程序员危机': '程序员/技术从业者/大学生',
            '流量获取': '运营人/市场人/创业者',
            '职场变化': '职场人/求职者/大学生',
            '自媒体变现': '自媒体人/博主/内容创作者',
        }
        
        return audience_map.get(topic, '职场人/创业者')
    
    def generate_with_llm(self, topics: List[Dict], conflicts: List[Dict]) -> List[TopicSuggestion]:
        """使用LLM生成选题建议
        
        Args:
            topics: 热点话题列表
            conflicts: 观点冲突列表
            
        Returns:
            选题建议列表
        """
        if not self.config.get('use_llm', False):
            logger.info("LLM生成未启用，使用模板生成")
            return self.generate_from_hot_topics(topics) + self.generate_from_conflicts(conflicts)
        
        # 构建提示
        prompt = self._build_llm_prompt(topics, conflicts)
        
        try:
            # 调用LLM
            response = self._call_llm(prompt)
            
            # 解析响应
            suggestions = self._parse_llm_response(response)
            
            logger.info(f"LLM生成 {len(suggestions)} 个选题建议")
            return suggestions
        except Exception as e:
            logger.error(f"LLM生成失败: {e}，回退到模板生成")
            return self.generate_from_hot_topics(topics) + self.generate_from_conflicts(conflicts)
    
    def _build_llm_prompt(self, topics: List[Dict], conflicts: List[Dict]) -> str:
        """构建LLM提示
        
        Args:
            topics: 热点话题
            conflicts: 观点冲突
            
        Returns:
            提示文本
        """
        prompt = """你是内容选题专家。请基于以下热点话题和观点冲突，生成10个有价值的选题建议。

## 热点话题
"""
        
        for i, topic in enumerate(topics, 1):
            prompt += f"""
{i}. {topic.get('topic_name', '')}
   - 关键词: {', '.join(topic.get('keywords', []))}
   - 相关内容: {topic.get('content_count', 0)}条
   - 来源: {', '.join(topic.get('sources', []))}
"""
        
        prompt += """
## 观点冲突
"""
        
        for i, conflict in enumerate(conflicts, 1):
            prompt += f"""
{i}. {conflict.get('topic', '')}
   - 观点A: {conflict.get('viewpoint_a', {}).get('viewpoint', '')}
   - 观点B: {conflict.get('viewpoint_b', {}).get('viewpoint', '')}
"""
        
        prompt += """
## 要求
1. 每个选题要有吸引力的标题
2. 给出切入角度
3. 列出关键要点
4. 建议内容格式和目标受众
5. 以JSON格式输出

输出格式：
[{"title": "选题标题", "angle": "切入角度", "key_points": ["要点1", "要点2"], "format": "观点/教程/故事", "audience": "目标受众"}]
"""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM
        
        Args:
            prompt: 提示文本
            
        Returns:
            LLM响应
        """
        # 这里需要根据不同的LLM提供商实现
        provider = self.llm_config.get('provider', 'coze')
        
        if provider == 'coze':
            # Coze API调用
            # 需要实现具体的API调用逻辑
            raise NotImplementedError("Coze API调用需要实现")
        elif provider == 'deepseek':
            # DeepSeek API调用
            raise NotImplementedError("DeepSeek API调用需要实现")
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")
    
    def _parse_llm_response(self, response: str) -> List[TopicSuggestion]:
        """解析LLM响应
        
        Args:
            response: LLM响应文本
            
        Returns:
            选题建议列表
        """
        try:
            data = json.loads(response)
            suggestions = []
            
            for i, item in enumerate(data):
                suggestion = TopicSuggestion(
                    topic_id=f"llm_{datetime.now().strftime('%Y%m%d')}_{i}",
                    title=item.get('title', ''),
                    angle=item.get('angle', ''),
                    source_topic='',
                    source_type='llm_generated',
                    key_points=item.get('key_points', []),
                    recommended_format=item.get('format', '观点'),
                    target_audience=item.get('audience', ''),
                    difficulty='medium',
                    estimated_read_time=5,
                    timestamp=datetime.now().isoformat()
                )
                suggestions.append(suggestion)
            
            return suggestions
        except Exception as e:
            logger.error(f"LLM响应解析失败: {e}")
            return []
    
    def format_suggestions(self, suggestions: List[TopicSuggestion]) -> str:
        """格式化选题建议
        
        Args:
            suggestions: 选题建议列表
            
        Returns:
            格式化文本
        """
        if not suggestions:
            return "暂无选题建议"
        
        lines = []
        lines.append("✏️ 建议选题\n━━━━━━━━━━━━━━━━━━━\n")
        
        for i, s in enumerate(suggestions, 1):
            lines.append(f"{i}️⃣ {s.title}")
            lines.append(f"   📐 角度：{s.angle}")
            lines.append(f"   📝 格式：{s.recommended_format} | 受众：{s.target_audience}")
            lines.append(f"   ⏱️ 预计阅读：{s.estimated_read_time}分钟")
            
            if s.key_points:
                lines.append(f"   💡 要点：")
                for point in s.key_points[:2]:
                    lines.append(f"      • {point}")
            lines.append("")
        
        return "\n".join(lines)
    
    def save_suggestions(self, suggestions: List[TopicSuggestion], week: str = None):
        """保存选题建议
        
        Args:
            suggestions: 选题建议列表
            week: 周标识
        """
        week = week or datetime.now().strftime('%Y-W%W')
        output_file = self.output_dir / f"选题建议_{week}.md"
        
        lines = [f"# 选题建议 | {week}\n"]
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("---\n")
        
        for i, s in enumerate(suggestions, 1):
            lines.append(f"## {i}. {s.title}")
            lines.append(f"- **角度**: {s.angle}")
            lines.append(f"- **来源**: {s.source_topic} ({s.source_type})")
            lines.append(f"- **格式**: {s.recommended_format}")
            lines.append(f"- **受众**: {s.target_audience}")
            lines.append(f"- **难度**: {s.difficulty}")
            lines.append(f"- **时长**: {s.estimated_read_time}分钟")
            if s.key_points:
                lines.append(f"- **要点**:")
                for p in s.key_points:
                    lines.append(f"  - {p}")
            lines.append("")
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            logger.info(f"选题建议已保存: {output_file}")
        except Exception as e:
            logger.error(f"选题建议保存失败: {e}")


def main():
    """测试函数"""
    generator = TopicGenerator()
    
    # 模拟热点话题
    hot_topics = [
        {
            'topic_name': 'AI创业',
            'keywords': ['AI', '创业', 'Agent'],
            'sources': ['张三', '李四'],
            'content_count': 5,
            'related_content': [
                {'viewpoint': 'AI创业机会很多，但要注意差异化竞争...'}
            ]
        },
        {
            'topic_name': '私域流量',
            'keywords': ['私域', '流量', '运营'],
            'sources': ['王五'],
            'content_count': 3,
            'related_content': [
                {'viewpoint': '私域运营需要长期坚持，不能急功近利...'}
            ]
        }
    ]
    
    # 模拟观点冲突
    conflicts = [
        {
            'topic': 'AI是否会取代程序员',
            'viewpoint_a': {'author': '张三', 'viewpoint': 'AI 5年内会写90%的代码'},
            'viewpoint_b': {'author': '李四', 'viewpoint': 'AI只是工具，创造力无法替代'}
        }
    ]
    
    # 生成选题
    suggestions = generator.generate_from_hot_topics(hot_topics)
    suggestions += generator.generate_from_conflicts(conflicts)
    
    print("\n" + "="*50)
    print("选题建议")
    print("="*50)
    print(generator.format_suggestions(suggestions))
    
    # 保存
    generator.save_suggestions(suggestions)


if __name__ == '__main__':
    main()
