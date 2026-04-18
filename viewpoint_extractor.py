#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
观点提取器 - 从转录稿中提取核心观点
使用LLM分析内容，提取关键信息
安全修复：添加内容过滤和长度限制，防止提示词注入
"""

import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 安全配置
MAX_TEXT_LENGTH = 50000  # 最大文本长度，防止超长输入
FORBIDDEN_PATTERNS = [
    r'ignore\s+(all\s+)?(previous|above)\s+(instructions?|prompts?)',
    r'system\s*:\s*you\s+are',
    r'forget\s+(all\s+)?(previous|above)',
    r'disregard\s+(all\s+)?(previous|above)',
    r'[\s\S]*?(\bprompt\b|\binstruction\b|\bsystem\b).*?:',
]


@dataclass
class ViewPoint:
    """观点数据类"""
    content: str           # 观点内容
    source: str            # 来源
    source_url: str        # 原文链接
    category: str          # 内容类型: 干货/观点/访谈/资讯
    highlights: List[str]  # 金句/亮点
    timestamp: str         # 提取时间


def sanitize_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """安全过滤文本，防止提示词注入
    
    Args:
        text: 原始文本
        max_length: 最大长度限制
        
    Returns:
        过滤后的安全文本
    """
    if not text:
        return ""
    
    # 长度限制
    if len(text) > max_length:
        logger.warning(f"文本过长({len(text)})，截断至{max_length}")
        text = text[:max_length]
    
    # 检测并移除潜在的提示词注入模式
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning(f"检测到潜在的提示词注入模式，已移除")
            text = re.sub(pattern, '[已过滤]', text, flags=re.IGNORECASE)
    
    return text.strip()


class ViewPointExtractor:
    """观点提取器主类
    
    从转录稿中提取：
    1. 核心观点（3-5条）
    2. 内容亮点/金句
    3. 内容类型判断
    
    安全说明：
    - 所有发送给LLM的文本都经过sanitize_text过滤
    - 限制最大文本长度，防止超长输入攻击
    - 检测并移除潜在的提示词注入模式
    """
    
    # 内容类型定义
    CONTENT_TYPES = {
        '干货': ['教程', '方法', '技巧', '指南', '教学', 'how to'],
        '观点': ['认为', '观点', '看法', '看法', '的角度', '观点是'],
        '访谈': ['对话', '采访', '访谈', '交流', '聊聊'],
        '资讯': ['报道', '新闻', '事件', '最新', '刚刚', '宣布'],
    }
    
    def __init__(self, llm_config: Optional[Dict] = None):
        """初始化观点提取器
        
        Args:
            llm_config: LLM配置
                - provider: 提供商 (coze/openai/claude/deepseek)
                - api_key: API密钥
                - model: 模型名称
        """
        self.llm_config = llm_config or self._load_llm_config()
        self.cache_dir = Path(__file__).parent.parent / "缓存" / "观点库"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_llm_config(self) -> Dict:
        """加载LLM配置"""
        config_path = Path(__file__).parent.parent / "配置" / "llm_config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 默认配置
        return {
            'provider': 'coze',
            'model': 'gpt-4o-mini',
            'temperature': 0.7,
        }
    
    def extract(self, 
                text: str, 
                source: str = "未知来源",
                source_url: str = "",
                max_points: int = 5) -> ViewPoint:
        """提取观点
        
        Args:
            text: 转录稿全文（会自动进行安全过滤）
            source: 来源名称
            source_url: 原文链接
            max_points: 最大观点数
            
        Returns:
            ViewPoint: 观点数据对象
        """
        logger.info(f"开始提取观点: {source}")
        
        # 安全过滤：防止提示词注入
        text = sanitize_text(text)
        
        # 检查缓存
        cache_key = self._get_cache_key(text)
        cached = self._load_from_cache(cache_key)
        if cached:
            logger.info(f"从缓存加载观点: {source}")
            cached.source = source
            cached.source_url = source_url
            return cached
        
        # 调用LLM提取
        try:
            result = self._call_llm_extract(text, max_points)
        except Exception as e:
            logger.error(f"LLM调用失败，使用规则提取: {e}")
            result = self._rule_based_extract(text)
        
        viewpoint = ViewPoint(
            content=result.get('content', ''),
            source=source,
            source_url=source_url,
            category=result.get('category', self._detect_category(text)),
            highlights=result.get('highlights', []),
            timestamp=datetime.now().isoformat(),
        )
        
        # 保存缓存
        self._save_to_cache(cache_key, viewpoint)
        
        return viewpoint
    
    def _call_llm_extract(self, text: str, max_points: int) -> Dict:
        """调用LLM提取观点
        
        使用结构化提示词，引导LLM输出JSON格式
        """
        provider = self.llm_config.get('provider', 'coze')
        
        if provider == 'coze':
            return self._call_coze(text, max_points)
        elif provider == 'deepseek':
            return self._call_deepseek(text, max_points)
        elif provider == 'openai':
            return self._call_openai(text, max_points)
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")
    
    def _call_coze(self, text: str, max_points: int) -> Dict:
        """调用Coze API"""
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=os.environ.get('COZE_API_KEY', ''),
                base_url="https://api.coze.cn/v1"
            )
            
            prompt = self._build_extract_prompt(text, max_points)
            
            response = client.chat.completions.create(
                model=self.llm_config.get('model', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": "你是一个内容分析专家，擅长从长文本中提取核心观点。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.llm_config.get('temperature', 0.7),
                response_format={"type": "json_object"},
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Coze API调用失败: {e}")
            raise
    
    def _call_deepseek(self, text: str, max_points: int) -> Dict:
        """调用DeepSeek API"""
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=os.environ.get('DEEPSEEK_API_KEY', ''),
                base_url="https://api.deepseek.com/v1"
            )
            
            prompt = self._build_extract_prompt(text, max_points)
            
            response = client.chat.completions.create(
                model=self.llm_config.get('model', 'deepseek-chat'),
                messages=[
                    {"role": "system", "content": "你是一个内容分析专家，擅长从长文本中提取核心观点。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.llm_config.get('temperature', 0.7),
                response_format={"type": "json_object"},
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {e}")
            raise
    
    def _call_openai(self, text: str, max_points: int) -> Dict:
        """调用OpenAI API"""
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=os.environ.get('OPENAI_API_KEY', '')
            )
            
            prompt = self._build_extract_prompt(text, max_points)
            
            response = client.chat.completions.create(
                model=self.llm_config.get('model', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": "你是一个内容分析专家，擅长从长文本中提取核心观点。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.llm_config.get('temperature', 0.7),
                response_format={"type": "json_object"},
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"OpenAI API调用失败: {e}")
            raise
    
    def _build_extract_prompt(self, text: str, max_points: int) -> str:
        """构建提取提示词"""
        # 限制文本长度，避免token溢出
        max_chars = 15000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[内容已截断...]"
        
        return f"""请分析以下内容，提取核心观点。

## 内容
{text}

## 输出要求
请以JSON格式输出，结构如下：
{{
    "summary": "内容摘要（100字内）",
    "category": "内容类型，只能是以下之一：干货/观点/访谈/资讯",
    "key_points": [
        "核心观点1（50字内）",
        "核心观点2（50字内）",
        "核心观点3（50字内）"
    ],
    "highlights": [
        "金句或亮点1",
        "金句或亮点2"
    ],
    "why_worth_watching": "为什么值得看/听（30字内）"
}}

请确保输出是有效的JSON格式。"""
    
    def _rule_based_extract(self, text: str) -> Dict:
        """基于规则的内容提取（LLM不可用时的降级方案）"""
        lines = text.split('\n')
        
        # 提取可能的关键句子
        important_patterns = [
            '认为', '观点是', '核心是', '关键在于', '重要的是',
            '第一', '第二', '第三', '总结一下', '总的来说',
            '所以', '因此', '这就是说', '换句话说'
        ]
        
        key_points = []
        highlights = []
        
        for line in lines:
            line = line.strip()
            if len(line) < 10 or len(line) > 200:
                continue
            
            # 检查是否匹配重要模式
            for pattern in important_patterns:
                if pattern in line:
                    key_points.append(line)
                    break
            
            # 提取可能的金句（带引号或特殊标记）
            if ('"' in line or '"' in line) and len(line) < 150:
                highlights.append(line)
        
        # 去重并限制数量
        key_points = list(dict.fromkeys(key_points))[:5]
        highlights = list(dict.fromkeys(highlights))[:3]
        
        return {
            'content': ' | '.join(key_points[:3]),
            'category': self._detect_category(text),
            'highlights': highlights,
            'key_points': key_points,
        }
    
    def _detect_category(self, text: str) -> str:
        """检测内容类型"""
        text_lower = text.lower()
        
        scores = {cat: 0 for cat in self.CONTENT_TYPES}
        
        for category, keywords in self.CONTENT_TYPES.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    scores[category] += 1
        
        # 返回得分最高的类型
        if max(scores.values()) == 0:
            return '观点'  # 默认类型
        
        return max(scores, key=scores.get)
    
    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        import hashlib
        return hashlib.md5(text[:500].encode()).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[ViewPoint]:
        """从缓存加载"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return ViewPoint(**data)
            except Exception as e:
                logger.warning(f"缓存读取失败: {e}")
        return None
    
    def _save_to_cache(self, cache_key: str, viewpoint: ViewPoint):
        """保存到缓存"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(viewpoint), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")
    
    def batch_extract(self, contents: List[Dict]) -> List[ViewPoint]:
        """批量提取观点
        
        Args:
            contents: 内容列表
                [
                    {"text": "转录稿", "source": "来源", "source_url": "链接"},
                    ...
                ]
                
        Returns:
            List[ViewPoint]: 观点列表
        """
        results = []
        
        for item in contents:
            try:
                viewpoint = self.extract(
                    text=item.get('text', ''),
                    source=item.get('source', '未知来源'),
                    source_url=item.get('source_url', ''),
                )
                results.append(viewpoint)
            except Exception as e:
                logger.error(f"观点提取失败 [{item.get('source', '未知')}]: {e}")
        
        return results


# 测试代码
if __name__ == '__main__':
    # 示例用法
    extractor = ViewPointExtractor()
    
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
    
    result = extractor.extract(sample_text, source="测试播客", source_url="https://example.com")
    
    print(f"类型: {result.category}")
    print(f"观点: {result.content}")
    print(f"亮点: {result.highlights}")
