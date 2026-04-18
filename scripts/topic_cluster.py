#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
话题聚类器 - 分析本周监控内容，识别热点话题
功能：
1. 分析本周所有监控内容
2. 按话题聚类，识别热点
3. 计算热度分数（讨论量+互动+时效性）
4. 输出：Top 3 热点话题
"""

import os
import json
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import Counter
import hashlib

# 配置日志
LOG_DIR = Path(__file__).parent.parent / "日志"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / f"topic_cluster_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TopicInfo:
    """话题信息类"""
    topic_id: str           # 话题ID
    topic_name: str         # 话题名称
    keywords: List[str]     # 关键词列表
    content_count: int       # 相关内容数量
    discussion_count: int    # 讨论量（提及次数）
    engagement_score: float  # 互动分数
    recency_score: float    # 时效性分数
    hotness_score: float    # 热度分数
    related_content: List[Dict]  # 相关内容列表
    sources: List[str]       # 来源博主
    timestamp: str           # 分析时间


class TopicCluster:
    """话题聚类器主类
    
    使用关键词提取 + 相似度匹配进行话题聚类
    热度分数 = 讨论量(40%) + 时效性(30%) + 互动(30%)
    """
    
    # 热点关键词（高频词）
    HOT_KEYWORDS = {
        # AI相关
        'AI', '人工智能', '大模型', 'LLM', 'ChatGPT', 'GPT', 'Gemini',
        'Agent', '智能体', '机器学习', '深度学习', '神经网络',
        'AI创业', 'AI应用', 'AI工具', 'AI产品',
        # 商业相关
        '创业', '融资', '投资', '商业', '变现', '赚钱', '商业模式',
        '创业公司', '独角兽', '估值', 'IPO', '上市',
        # 流量相关
        '私域', '流量', '增长', '获客', '转化', '裂变',
        '私域流量', '私域运营', '私域电商',
        # 职场相关
        '程序员', '开发', '产品经理', '运营', '市场',
        '就业', '裁员', '招聘', '薪资', '打工',
        # 社交媒体
        '小红书', '抖音', '微信', '视频号', 'B站',
        '自媒体', '博主', 'KOL', '网红',
    }
    
    # 话题关键词映射
    TOPIC_KEYWORDS = {
        'AI创业': ['AI创业', '人工智能创业', '大模型创业', 'LLM创业', 'Agent创业', '智能体创业'],
        '私域流量': ['私域', '私域流量', '私域运营', '私域电商', '私域2.0'],
        '程序员危机': ['程序员', '程序员失业', '程序员转型', 'AI写代码', 'AI编程'],
        '流量获取': ['流量获取', '获客', '增长黑客', '裂变', '病毒传播'],
        '职场变化': ['裁员', '降薪', '失业', '就业难', '35岁危机', '中年危机'],
        '自媒体变现': ['自媒体变现', '博主变现', '内容变现', '知识付费', '带货'],
        'AI应用': ['AI应用', 'AI工具', 'AI产品', 'AI落地'],
        '创业融资': ['融资', '投资', '创业融资', 'VC', '风投'],
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化话题聚类器
        
        Args:
            config: 配置字典
        """
        self.config = config or self._load_config()
        self.base_dir = Path(__file__).parent.parent
        self.cache_dir = self.base_dir / "缓存" / "话题库"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 历史话题存储
        self.history_file = self.cache_dir / "topic_history.json"
        self.history = self._load_history()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        config_path = self.base_dir / "配置" / "选题配置.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"配置加载失败: {e}")
        
        # 默认配置
        return {
            'hot_threshold': 5,           # 热点话题最小提及数
            'top_n': 3,                   # 返回Top N热点话题
            'recency_days': 7,             # 时效性计算天数
            'engagement_weight': 0.3,     # 互动权重
            'recency_weight': 0.3,       # 时效性权重
            'discussion_weight': 0.4,    # 讨论量权重
        }
    
    def _load_history(self) -> List[Dict]:
        """加载历史话题"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"历史话题加载失败: {e}")
        return []
    
    def _save_history(self):
        """保存历史话题"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            logger.info(f"历史话题已保存，共 {len(self.history)} 条")
        except Exception as e:
            logger.error(f"历史话题保存失败: {e}")
    
    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词
        
        Args:
            text: 输入文本
            
        Returns:
            关键词列表
        """
        if not text:
            return []
        
        # 清理文本
        text = text.lower()
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        
        # 提取热点关键词
        keywords = []
        for keyword in self.HOT_KEYWORDS:
            if keyword.lower() in text:
                keywords.append(keyword)
        
        # 提取话题关键词
        for topic, topic_kws in self.TOPIC_KEYWORDS.items():
            for kw in topic_kws:
                if kw.lower() in text:
                    if topic not in keywords:
                        keywords.append(topic)
                    break
        
        return list(set(keywords))
    
    def _calculate_recency_score(self, content_date: datetime) -> float:
        """计算时效性分数
        
        Args:
            content_date: 内容日期
            
        Returns:
            时效性分数 (0-1)
        """
        days_ago = (datetime.now() - content_date).days
        if days_ago <= 1:
            return 1.0
        elif days_ago <= 3:
            return 0.8
        elif days_ago <= 7:
            return 0.6
        elif days_ago <= 14:
            return 0.4
        else:
            return 0.2
    
    def _calculate_engagement_score(self, content: Dict) -> float:
        """计算互动分数
        
        Args:
            content: 内容字典
            
        Returns:
            互动分数 (0-1)
        """
        # 从内容中提取互动数据
        views = content.get('views', 0) or 0
        likes = content.get('likes', 0) or 0
        comments = content.get('comments', 0) or 0
        shares = content.get('shares', 0) or 0
        
        # 标准化计算
        engagement = (likes * 1 + comments * 2 + shares * 3) / max(views, 1)
        
        # 映射到0-1范围
        score = min(engagement * 10, 1.0)
        return score
    
    def _calculate_hotness_score(self, 
                                  discussion_count: int, 
                                  recency_scores: List[float],
                                  engagement_scores: List[float]) -> float:
        """计算热度分数
        
        Args:
            discussion_count: 讨论量
            recency_scores: 时效性分数列表
            engagement_scores: 互动分数列表
            
        Returns:
            热度分数
        """
        # 讨论量分数（归一化）
        discussion_score = min(discussion_count / 20, 1.0)  # 假设20次为满分
        
        # 平均时效性分数
        avg_recency = sum(recency_scores) / len(recency_scores) if recency_scores else 0
        
        # 平均互动分数
        avg_engagement = sum(engagement_scores) / len(engagement_scores) if engagement_scores else 0
        
        # 综合计算
        weights = self.config
        hotness = (
            discussion_score * weights.get('discussion_weight', 0.4) +
            avg_recency * weights.get('recency_weight', 0.3) +
            avg_engagement * weights.get('engagement_weight', 0.3)
        )
        
        return round(hotness, 3)
    
    def _cluster_topics(self, content_list: List[Dict]) -> Dict[str, List[Dict]]:
        """对话题进行聚类
        
        Args:
            content_list: 内容列表
            
        Returns:
            话题字典 {topic_name: [content_list]}
        """
        topic_clusters = {}
        
        for content in content_list:
            # 提取关键词
            title = content.get('title', '')
            description = content.get('description', '')
            viewpoint = content.get('viewpoint', '')
            text = f"{title} {description} {viewpoint}"
            
            keywords = self._extract_keywords(text)
            
            # 匹配话题
            matched = False
            for topic, topic_kws in self.TOPIC_KEYWORDS.items():
                for kw in topic_kws:
                    if kw.lower() in text.lower():
                        if topic not in topic_clusters:
                            topic_clusters[topic] = []
                        topic_clusters[topic].append(content)
                        matched = True
                        break
                if matched:
                    break
            
            # 未匹配的内容按关键词聚合
            if not matched and keywords:
                # 使用第一个关键词作为话题名
                topic_name = keywords[0]
                if topic_name not in topic_clusters:
                    topic_clusters[topic_name] = []
                topic_clusters[topic_name].append(content)
        
        return topic_clusters
    
    def analyze(self, content_list: List[Dict], week_offset: int = 0) -> List[TopicInfo]:
        """分析内容，识别热点话题
        
        Args:
            content_list: 内容列表
            week_offset: 周偏移量（0=本周，-1=上周，1=下周）
            
        Returns:
            热点话题列表
        """
        if not content_list:
            logger.warning("没有内容可供分析")
            return []
        
        logger.info(f"开始分析 {len(content_list)} 条内容...")
        
        # 聚类话题
        topic_clusters = self._cluster_topics(content_list)
        logger.info(f"发现 {len(topic_clusters)} 个话题")
        
        # 计算每个话题的热度
        topic_infos = []
        for topic_name, contents in topic_clusters.items():
            if len(contents) < self.config.get('hot_threshold', 1):
                continue
            
            # 提取来源
            sources = list(set([c.get('author', '未知') for c in contents]))
            
            # 计算时效性分数
            recency_scores = []
            for c in contents:
                date_str = c.get('date', '') or c.get('published', '')
                try:
                    if date_str:
                        content_date = datetime.strptime(date_str[:10], '%Y-%m-%d')
                        recency_scores.append(self._calculate_recency_score(content_date))
                except:
                    recency_scores.append(0.5)
            
            # 计算互动分数
            engagement_scores = [self._calculate_engagement_score(c) for c in contents]
            
            # 计算热度分数
            hotness_score = self._calculate_hotness_score(
                len(contents),
                recency_scores,
                engagement_scores
            )
            
            # 计算本周增长率（对比历史）
            growth_rate = self._calculate_growth_rate(topic_name, len(contents))
            
            # 提取关键词
            keywords = []
            for c in contents:
                text = f"{c.get('title', '')} {c.get('viewpoint', '')}"
                keywords.extend(self._extract_keywords(text))
            keywords = list(set(keywords))[:5]  # 取前5个
            
            # 生成话题ID
            topic_id = hashlib.md5(topic_name.encode()).hexdigest()[:8]
            
            topic_info = TopicInfo(
                topic_id=topic_id,
                topic_name=topic_name,
                keywords=keywords,
                content_count=len(contents),
                discussion_count=len(contents),
                engagement_score=round(sum(engagement_scores) / len(engagement_scores), 3) if engagement_scores else 0,
                recency_score=round(sum(recency_scores) / len(recency_scores), 3) if recency_scores else 0,
                hotness_score=hotness_score,
                related_content=contents[:5],  # 最多5条
                sources=sources,
                timestamp=datetime.now().isoformat()
            )
            
            topic_infos.append(topic_info)
        
        # 按热度排序
        topic_infos.sort(key=lambda x: x.hotness_score, reverse=True)
        
        # 取Top N
        top_n = self.config.get('top_n', 3)
        top_topics = topic_infos[:top_n]
        
        logger.info(f"Top {len(top_topics)} 热点话题: {[t.topic_name for t in top_topics]}")
        
        # 更新历史
        self._update_history(top_topics)
        
        return top_topics
    
    def _calculate_growth_rate(self, topic_name: str, current_count: int) -> float:
        """计算话题增长率
        
        Args:
            topic_name: 话题名称
            current_count: 本周数量
            
        Returns:
            增长率 (0.0 = 无增长，1.0 = 翻倍)
        """
        # 从历史中查找该话题
        for history in self.history[-4:]:  # 只看最近4周
            if history.get('topic_name') == topic_name:
                prev_count = history.get('content_count', 0)
                if prev_count > 0:
                    return round((current_count - prev_count) / prev_count, 2)
        
        return 0.0
    
    def _update_history(self, topics: List[TopicInfo]):
        """更新历史话题
        
        Args:
            topics: 本期热点话题
        """
        week_key = datetime.now().strftime('%Y-W%W')
        
        for topic in topics:
            topic_dict = {
                'week': week_key,
                'topic_id': topic.topic_id,
                'topic_name': topic.topic_name,
                'content_count': topic.content_count,
                'hotness_score': topic.hotness_score,
                'timestamp': topic.timestamp,
            }
            
            # 检查是否已存在
            exists = False
            for i, h in enumerate(self.history):
                if h.get('topic_name') == topic.topic_name and h.get('week') == week_key:
                    self.history[i] = topic_dict
                    exists = True
                    break
            
            if not exists:
                self.history.append(topic_dict)
        
        # 保留最近8周历史
        self.history = self.history[-56:]  # 8周 * 7条
        
        self._save_history()
    
    def get_topic_report(self, topics: List[TopicInfo]) -> str:
        """生成话题报告
        
        Args:
            topics: 热点话题列表
            
        Returns:
            话题报告文本
        """
        if not topics:
            return "本周未发现明显热点话题"
        
        report_lines = []
        report_lines.append("🔥 热点话题\n━━━━━━━━━━━━━━━━━━━\n")
        
        for i, topic in enumerate(topics, 1):
            # 计算增长率
            growth_rate = self._calculate_growth_rate(topic.topic_name, topic.content_count)
            growth_str = f"+{int(growth_rate * 100)}%" if growth_rate > 0 else f"{int(growth_rate * 100)}%"
            
            report_lines.append(f"{i}️⃣ {topic.topic_name}")
            report_lines.append(f"   📊 热度：讨论{topic.discussion_count}条，本周增长{growth_str}")
            report_lines.append(f"   💡 切入角度：")
            
            # 生成切入角度
            angles = self._generate_angles(topic)
            for angle in angles:
                report_lines.append(f"      - {angle}")
            
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def _generate_angles(self, topic: TopicInfo) -> List[str]:
        """生成切入角度建议
        
        Args:
            topic: 话题信息
            
        Returns:
            切入角度列表
        """
        angles = []
        
        # 基于话题生成角度
        topic_name = topic.topic_name
        
        if 'AI' in topic_name or '程序员' in topic_name:
            angles.extend([
                "技术视角：技术壁垒在哪里？",
                "商业视角：商业模式的可行性",
                "人文视角：对从业者的影响"
            ])
        elif '私域' in topic_name or '流量' in topic_name:
            angles.extend([
                "经验视角：我做私域的实战经验",
                "辩论视角：私域已死 vs 私域2.0",
                "案例视角：成功/失败的私域案例"
            ])
        elif '创业' in topic_name:
            angles.extend([
                "创始人视角：创业路上的坑",
                "投资人视角：什么样的项目值得投",
                "对比视角：国内外创业环境差异"
            ])
        elif '职场' in topic_name or '裁员' in topic_name:
            angles.extend([
                "当事人视角：被裁后的真实经历",
                "建议视角：如何避免被裁",
                "思考视角：职场人的出路在哪里"
            ])
        else:
            angles.extend([
                "是什么：这个现象的本质",
                "为什么：背后的原因分析",
                "怎么办：如何应对或利用"
            ])
        
        return angles[:3]  # 最多3个角度


def main():
    """主函数 - 用于测试"""
    import sys
    
    # 模拟数据
    test_contents = [
        {
            'title': 'AI创业的3个机会',
            'author': '张三',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'views': 10000,
            'likes': 500,
            'comments': 100,
            'viewpoint': 'AI创业机会很多，但要注意差异化...'
        },
        {
            'title': '程序员如何面对AI替代',
            'author': '李四',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'views': 8000,
            'likes': 400,
            'comments': 80,
            'viewpoint': 'AI会替代部分程序员工作，但创造力无法替代...'
        },
        {
            'title': '私域流量运营实战',
            'author': '王五',
            'date': (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d'),
            'views': 5000,
            'likes': 200,
            'comments': 50,
            'viewpoint': '私域运营需要长期坚持...'
        },
    ]
    
    cluster = TopicCluster()
    topics = cluster.analyze(test_contents)
    
    print("\n" + "="*50)
    print("话题聚类分析结果")
    print("="*50)
    
    for topic in topics:
        print(f"\n📌 {topic.topic_name}")
        print(f"   热度分数: {topic.hotness_score}")
        print(f"   内容数量: {topic.content_count}")
        print(f"   关键词: {', '.join(topic.keywords)}")


if __name__ == '__main__':
    main()
