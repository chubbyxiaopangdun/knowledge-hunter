#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容评分器 - 对内容进行质量评分
基于观点质量、信息密度、原创性等维度打分
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ContentScore:
    """内容评分数据类"""
    source: str                    # 内容来源
    source_url: str                 # 原文链接
    total_score: float             # 总分 (0-10)
    viewpoint_quality: float       # 观点质量分
    info_density: float            # 信息密度分
    originality: float            # 原创性分
    is_worth_consuming: bool      # 是否值得消费
    recommendation: str            # 推荐语
    category: str                   # 内容类型
    timestamp: str                  # 评分时间


class ContentScorer:
    """内容评分器主类
    
    评分维度：
    1. 观点质量 (0-10): 观点是否清晰、有深度、有价值
    2. 信息密度 (0-10): 单位时间内信息量多少
    3. 原创性 (0-10): 是否有独特见解、新鲜信息
    
    综合评分 = 观点质量 * 0.4 + 信息密度 * 0.3 + 原创性 * 0.3
    
    标记规则：
    - >=8.0: 强烈推荐 "⭐⭐⭐⭐⭐"
    - >=7.0: 推荐 "⭐⭐⭐⭐"
    - >=6.0: 可以看 "⭐⭐⭐"
    - >=5.0: 一般 "⭐⭐"
    - <5.0: 不推荐
    """
    
    # 评分规则配置
    DEFAULT_RULES = {
        # 观点质量规则
        'viewpoint': {
            'has_clear_viewpoint': 2.0,      # 有明确观点
            'has_examples': 1.5,             # 有案例支撑
            'has_depth': 2.0,                # 有深度分析
            'has_actionable': 1.5,            # 有可执行建议
            'has_unique_angle': 2.0,          # 有独特角度
            'has_logic_chain': 1.0,           # 有逻辑链条
        },
        # 信息密度规则
        'info_density': {
            'no_filler': 2.0,                # 无废话
            'data_driven': 2.0,               # 有数据支撑
            'multi_perspective': 2.0,         # 多角度分析
            'structured': 2.0,                # 结构清晰
            'dense_content': 2.0,             # 内容充实
        },
        # 原创性规则
        'originality': {
            'new_insight': 3.0,               # 新见解
            'fresh_data': 2.0,                # 新数据
            'unique_perspective': 3.0,        # 独特视角
            'contrarian_view': 2.0,           # 反共识观点
        }
    }
    
    def __init__(self, rules: Optional[Dict] = None):
        """初始化评分器
        
        Args:
            rules: 自定义评分规则
        """
        self.rules = rules or self._load_rules()
        self.cache_dir = Path(__file__).parent.parent / "缓存" / "评分库"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_rules(self) -> Dict:
        """加载评分规则"""
        config_path = Path(__file__).parent.parent / "配置" / "评分规则.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self.DEFAULT_RULES
    
    def score(self,
              text: str,
              viewpoint: Optional[Dict] = None,
              source: str = "未知来源",
              source_url: str = "") -> ContentScore:
        """对内容进行评分
        
        Args:
            text: 内容文本
            viewpoint: 观点提取结果（可选）
            source: 来源名称
            source_url: 原文链接
            
        Returns:
            ContentScore: 评分结果
        """
        logger.info(f"开始评分: {source}")
        
        # 基础规则评分
        viewpoint_score = self._score_viewpoint(text, viewpoint)
        density_score = self._score_info_density(text)
        originality_score = self._score_originality(text)
        
        # 计算总分
        total = (
            viewpoint_score * 0.4 +
            density_score * 0.3 +
            originality_score * 0.3
        )
        
        # 判断是否值得消费
        is_worth = total >= 6.0
        
        # 生成推荐语
        recommendation = self._generate_recommendation(total, viewpoint)
        
        category = viewpoint.get('category', '观点') if viewpoint else '观点'
        
        return ContentScore(
            source=source,
            source_url=source_url,
            total_score=round(total, 1),
            viewpoint_quality=round(viewpoint_score, 1),
            info_density=round(density_score, 1),
            originality=round(originality_score, 1),
            is_worth_consuming=is_worth,
            recommendation=recommendation,
            category=category,
            timestamp=datetime.now().isoformat(),
        )
    
    def _score_viewpoint(self, text: str, viewpoint: Optional[Dict]) -> float:
        """评分观点质量"""
        max_score = sum(self.rules['viewpoint'].values())
        score = 0.0
        
        text_lower = text.lower()
        
        # 有明确观点
        viewpoint_keywords = ['认为', '观点是', '看法是', '我觉得', '关键在于', '核心是']
        if any(kw in text_lower for kw in viewpoint_keywords):
            score += self.rules['viewpoint']['has_clear_viewpoint']
        
        # 有案例支撑
        example_keywords = ['比如', '例如', '举个例子', '案例', '有个', '比如我']
        if any(kw in text_lower for kw in example_keywords):
            score += self.rules['viewpoint']['has_examples']
        
        # 有深度分析
        depth_keywords = ['分析', '原因', '本质', '背后', '更深层', '底层逻辑']
        if any(kw in text_lower for kw in depth_keywords):
            score += self.rules['viewpoint']['has_depth']
        
        # 有可执行建议
        action_keywords = ['应该', '可以尝试', '建议', '建议是', '最好', '要']
        if any(kw in text_lower for kw in action_keywords):
            score += self.rules['viewpoint']['has_actionable']
        
        # 有独特角度
        unique_keywords = ['其实', '实际上', '但其实', '不同的是', '换个角度']
        if any(kw in text_lower for kw in unique_keywords):
            score += self.rules['viewpoint']['has_unique_angle']
        
        # 有逻辑链条
        logic_keywords = ['因为', '所以', '因此', '导致', '结果', '第一', '第二', '第三']
        if any(kw in text_lower for kw in logic_keywords):
            score += self.rules['viewpoint']['has_logic_chain']
        
        # 如果有LLM提取的观点，增加分数
        if viewpoint and viewpoint.get('key_points'):
            score += 1.0
        
        return min(score, max_score) / max_score * 10
    
    def _score_info_density(self, text: str) -> float:
        """评分信息密度"""
        max_score = sum(self.rules['info_density'].values())
        score = 0.0
        
        text_lower = text.lower()
        
        # 无废话（计算有效内容比例）
        filler_words = ['嗯', '啊', '这个', '那个', '的话', '就是', '怎么说呢']
        filler_count = sum(text.count(fw) for fw in filler_words)
        text_length = len(text)
        filler_ratio = filler_count / (text_length / 100) if text_length > 0 else 0
        if filler_ratio < 5:  # 废话比例低
            score += self.rules['info_density']['no_filler']
        
        # 有数据支撑
        data_patterns = ['%', '倍', '增长了', '下降了', '数据', '统计', '研究显示']
        if any(p in text_lower for p in data_patterns):
            score += self.rules['info_density']['data_driven']
        
        # 多角度分析
        angle_keywords = ['一方面', '另一方面', '从x角度看', '除了', '此外']
        if any(kw in text_lower for kw in angle_keywords):
            score += self.rules['info_density']['multi_perspective']
        
        # 结构清晰
        structure_keywords = ['第一', '第二', '第三', '首先', '其次', '最后', '总结']
        if any(kw in text_lower for kw in structure_keywords):
            score += self.rules['info_density']['structured']
        
        # 内容充实（字数适中，不过短也不过长）
        char_count = len(text)
        if 1000 <= char_count <= 50000:
            score += self.rules['info_density']['dense_content']
        elif 500 <= char_count < 1000:
            score += self.rules['info_density']['dense_content'] * 0.5
        
        return min(score, max_score) / max_score * 10
    
    def _score_originality(self, text: str) -> float:
        """评分原创性"""
        max_score = sum(self.rules['originality'].values())
        score = 0.0
        
        text_lower = text.lower()
        
        # 新见解
        insight_keywords = ['我发现', '新的', '创新', '首次', '突破', '不一样']
        if any(kw in text_lower for kw in insight_keywords):
            score += self.rules['originality']['new_insight']
        
        # 新数据
        fresh_keywords = ['最新', '最近', '刚刚', '今年', '去年', '2024', '2025', '2026']
        if any(kw in text_lower for kw in fresh_keywords):
            score += self.rules['originality']['fresh_data']
        
        # 独特视角
        unique_keywords = ['其实', '但实际上', '不同于', '反过来', '其实不然']
        if any(kw in text_lower for kw in unique_keywords):
            score += self.rules['originality']['unique_perspective']
        
        # 反共识观点
        contrarian_keywords = ['其实不是', '不一定', '可能错了', '与传统观点', '但事实是']
        if any(kw in text_lower for kw in contrarian_keywords):
            score += self.rules['originality']['contrarian_view']
        
        return min(score, max_score) / max_score * 10
    
    def _generate_recommendation(self, score: float, viewpoint: Optional[Dict]) -> str:
        """生成推荐语"""
        why_worth = ""
        if viewpoint:
            why_worth = viewpoint.get('why_worth_watching', '')
        
        if score >= 8.0:
            return f"⭐⭐⭐⭐⭐ 强烈推荐！{why_worth}" if why_worth else "⭐⭐⭐⭐⭐ 强烈推荐！"
        elif score >= 7.0:
            return f"⭐⭐⭐⭐ 推荐观看，{why_worth}" if why_worth else "⭐⭐⭐⭐ 推荐观看"
        elif score >= 6.0:
            return "⭐⭐⭐ 可以一看"
        elif score >= 5.0:
            return "⭐⭐ 内容一般"
        else:
            return "⭐ 不推荐"
    
    def batch_score(self, contents: List[Dict]) -> List[ContentScore]:
        """批量评分
        
        Args:
            contents: 内容列表
                [
                    {"text": "内容文本", "source": "来源", "source_url": "链接", "viewpoint": {...}},
                    ...
                ]
                
        Returns:
            List[ContentScore]: 评分结果列表
        """
        results = []
        
        for item in contents:
            try:
                score = self.score(
                    text=item.get('text', ''),
                    viewpoint=item.get('viewpoint'),
                    source=item.get('source', '未知来源'),
                    source_url=item.get('source_url', ''),
                )
                results.append(score)
            except Exception as e:
                logger.error(f"评分失败 [{item.get('source', '未知')}]: {e}")
        
        return results
    
    def get_top_contents(self, scores: List[ContentScore], top_n: int = 5) -> List[ContentScore]:
        """获取评分最高的内容
        
        Args:
            scores: 评分结果列表
            top_n: 返回数量
            
        Returns:
            List[ContentScore]: 排序后的TOP N
        """
        # 只选择值得消费的内容
        worth_contents = [s for s in scores if s.is_worth_consuming]
        
        # 按总分排序
        sorted_contents = sorted(
            worth_contents,
            key=lambda x: x.total_score,
            reverse=True
        )
        
        return sorted_contents[:top_n]
    
    def save_scores(self, scores: List[ContentScore], date: Optional[str] = None):
        """保存评分结果
        
        Args:
            scores: 评分列表
            date: 日期字符串，默认为今天
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        output_dir = Path(__file__).parent.parent / "输出" / "评分"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"scores_{date}.json"
        
        data = {
            'date': date,
            'scores': [asdict(s) for s in scores]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"评分结果已保存: {output_file}")


# 辅助函数
def asdict(obj):
    """将dataclass转换为dict"""
    if hasattr(obj, '__dataclass_fields__'):
        return {k: asdict(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, list):
        return [asdict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: asdict(v) for k, v in obj.items()}
    return obj


# 测试代码
if __name__ == '__main__':
    scorer = ContentScorer()
    
    sample_text = """
    今天我们来聊聊AI时代的创业机会。
    
    我认为，未来3年，AI Agent将成为创业新赛道。为什么这么说呢？
    
    第一，技术的成熟度已经达到了可商用的阶段。大模型的能力在不断提升，而成本却在持续下降。
    第二，市场需求非常明确。企业需要自动化解决方案，个人需要智能助手。
    第三，商业模式清晰。从工具到订阅，从API到定制化服务，有很多变现路径。
    
    举个例子，我认识的一个团队，他们做的是AI客服，现在月收入已经突破了100万。
    
    当然，挑战也是有的。数据隐私、安全合规、技术门槛，这些都是需要考虑的问题。
    
    总结一下，如果你想创业，AI Agent方向值得关注，但要想清楚自己的差异化在哪里。
    """
    
    result = scorer.score(sample_text, source="测试播客")
    
    print(f"总分: {result.total_score}")
    print(f"观点质量: {result.viewpoint_quality}")
    print(f"信息密度: {result.info_density}")
    print(f"原创性: {result.originality}")
    print(f"推荐: {result.recommendation}")
