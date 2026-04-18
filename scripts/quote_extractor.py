#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
金句提取器 - 从转录稿中提取金句
使用LLM分析内容，提取可用于内容创作的精彩语句
"""

import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict, field

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
class Quote:
    """金句数据类"""
    text: str                    # 金句原文
    topic: str                    # 主题标签
    source_title: str            # 来源标题
    source_author: str           # 来源作者
    source_url: str              # 原文链接
    platform: str                # 平台名称
    created_at: str              # 提取时间
    context: str = ""            # 上下文/使用场景
    usage: str = ""              # 使用建议
    
    def to_markdown(self) -> str:
        """转换为Markdown格式"""
        lines = [
            f"> {self.text}",
            "",
            f"- **主题**: {self.topic}",
            f"- **来源**: [{self.source_title}]({self.source_url}) - {self.source_author}",
            f"- **平台**: {self.platform}",
        ]
        if self.usage:
            lines.append(f"- **使用建议**: {self.usage}")
        return '\n'.join(lines)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


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


class QuoteExtractor:
    """金句提取器主类
    
    从转录稿中提取金句：
    1. 精准有力的观点表达
    2. 富有洞察的洞察陈述
    3. 情感共鸣的语句
    4. 可直接引用的精彩论述
    
    特点：
    - 每段内容提取约20个金句
    - 自动打标签（主题分类）
    - 记录来源信息
    - 成本优化：使用gpt-4o-mini模型
    """
    
    # 默认主题标签
    DEFAULT_TOPICS = [
        "创业", "投资", "职场", "技术", "产品", "运营",
        "增长", "管理", "营销", "品牌", "人生", "成长",
        "情感", "健康", "生活", "AI", "商业", "趋势"
    ]
    
    # 金句类型定义
    QUOTE_TYPES = [
        "洞察类",      # 有深度洞察的句子
        "观点类",      # 表达鲜明观点
        "方法类",      # 提供方法论
        "金句类",      # 朗朗上口可直接引用
        "情感类",      # 情感共鸣
        "警示类",      # 警示提醒
        "启发类",      # 启发思考
    ]
    
    def __init__(self, llm_config: Optional[Dict] = None, quotes_per_video: int = 20):
        """初始化金句提取器
        
        Args:
            llm_config: LLM配置
                - provider: 提供商 (coze/openai/deepseek)
                - api_key: API密钥
                - base_url: API基础地址（可选）
                - model: 模型名称（默认gpt-4o-mini）
            quotes_per_video: 每个视频提取的金句数量
        """
        self.quotes_per_video = quotes_per_video
        self.llm_config = llm_config or self._load_default_config()
        
        # 支持的提供商
        self._providers = {
            'coze': self._call_coze,
            'openai': self._call_openai,
            'deepseek': self._call_deepseek,
        }
    
    def _load_default_config(self) -> Dict:
        """加载默认配置"""
        config = {}
        
        # 尝试从环境变量加载
        if os.getenv('OPENAI_API_KEY'):
            config['provider'] = 'openai'
            config['api_key'] = os.getenv('OPENAI_API_KEY')
            config['base_url'] = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
            config['model'] = os.getenv('QUOTE_MODEL', 'gpt-4o-mini')
        elif os.getenv('DEEPSEEK_API_KEY'):
            config['provider'] = 'deepseek'
            config['api_key'] = os.getenv('DEEPSEEK_API_KEY')
            config['model'] = os.getenv('QUOTE_MODEL', 'gpt-4o-mini')
        else:
            config['provider'] = 'coze'
            config['model'] = os.getenv('QUOTE_MODEL', 'gpt-4o-mini')
        
        return config
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的金句提取专家，负责从内容中提取有价值、可引用的精彩语句。

## 你的任务
从给定的文本中提取金句，每段内容提取约20个金句。

## 金句标准
1. **精准有力**：表达精准、有力量感
2. **有洞察**：包含有价值的思想或洞察
3. **可引用**：可以直接用于内容创作的句子
4. **多样化**：涵盖不同类型（观点、方法、情感等）

## 输出格式（JSON数组）
```json
[
  {
    "text": "金句原文",
    "topic": "主题标签",
    "type": "金句类型",
    "usage": "使用建议（可选）"
  }
]
```

## 要求
- 严格返回JSON数组，不要包含其他内容
- 每个金句控制在50字以内
- 确保金句完整，不要截断
- topic从以下标签中选择：创业,投资,职场,技术,产品,运营,增长,管理,营销,品牌,人生,成长,情感,健康,生活,AI,商业,趋势,其他
- type可选：洞察类,观点类,方法类,金句类,情感类,警示类,启发类

## 注意事项
- 只提取真正有价值的句子，不要为了凑数而提取
- 保持原文的表达风格和语气
- 注意句子的完整性和独立性
"""
    
    def _get_user_prompt(self, text: str, source_title: str) -> str:
        """获取用户提示词"""
        return f"""请从以下内容中提取金句：

---
标题：{source_title}
---

{text}

---
请提取{self.quotes_per_video}个金句，返回JSON数组格式。
"""
    
    def _call_coze(self, messages: List[Dict]) -> str:
        """调用Coze API"""
        try:
            import httpx
            
            api_key = os.getenv('AGENT_AUTH_API_KEY', '')
            if not api_key:
                raise ValueError("未配置Coze API Key")
            
            # 构建请求
            payload = {
                "model": self.llm_config.get('model', 'gpt-4o-mini'),
                "messages": messages,
                "temperature": 0.7,
            }
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            
            # 尝试调用Coze API
            # 注意：这里需要根据实际情况调整API端点
            response = httpx.post(
                "https://api.coze.cn/v1/chat",
                json=payload,
                headers=headers,
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('choices', [{}])[0].get('message', {}).get('content', '')
            else:
                raise Exception(f"API返回错误: {response.status_code}")
                
        except ImportError:
            raise ImportError("请安装httpx库: pip install httpx")
        except Exception as e:
            raise Exception(f"Coze API调用失败: {e}")
    
    def _call_openai(self, messages: List[Dict]) -> str:
        """调用OpenAI API"""
        try:
            import httpx
            
            api_key = self.llm_config.get('api_key')
            base_url = self.llm_config.get('base_url', 'https://api.openai.com/v1')
            model = self.llm_config.get('model', 'gpt-4o-mini')
            
            if not api_key:
                raise ValueError("未配置OpenAI API Key")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
            }
            
            response = httpx.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                raise Exception(f"API返回错误: {response.status_code} - {response.text}")
                
        except ImportError:
            raise ImportError("请安装httpx库: pip install httpx")
        except Exception as e:
            raise Exception(f"OpenAI API调用失败: {e}")
    
    def _call_deepseek(self, messages: List[Dict]) -> str:
        """调用DeepSeek API"""
        try:
            import httpx
            
            api_key = self.llm_config.get('api_key')
            model = self.llm_config.get('model', 'deepseek-chat')
            
            if not api_key:
                raise ValueError("未配置DeepSeek API Key")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
            }
            
            response = httpx.post(
                "https://api.deepseek.com/chat/completions",
                json=payload,
                headers=headers,
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                raise Exception(f"API返回错误: {response.status_code} - {response.text}")
                
        except ImportError:
            raise ImportError("请安装httpx库: pip install httpx")
        except Exception as e:
            raise Exception(f"DeepSeek API调用失败: {e}")
    
    def _call_llm(self, text: str, source_title: str) -> str:
        """调用LLM提取金句"""
        provider = self.llm_config.get('provider', 'coze')
        
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": self._get_user_prompt(text, source_title)},
        ]
        
        if provider in self._providers:
            return self._providers[provider](messages)
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")
    
    def _parse_json_response(self, response: str) -> List[Dict]:
        """解析JSON响应"""
        # 尝试提取JSON数组
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # 尝试解析整个响应
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        logger.warning(f"无法解析LLM响应: {response[:200]}...")
        return []
    
    def extract(
        self,
        text: str,
        source_title: str,
        source_author: str = "",
        source_url: str = "",
        platform: str = ""
    ) -> List[Quote]:
        """从文本中提取金句
        
        Args:
            text: 转录文本内容
            source_title: 来源标题
            source_author: 来源作者（可选）
            source_url: 原文链接（可选）
            platform: 平台名称（可选）
            
        Returns:
            List[Quote]: 金句列表
        """
        if not text or len(text) < 50:
            logger.warning("文本内容过短，跳过金句提取")
            return []
        
        # 安全过滤
        safe_text = sanitize_text(text)
        
        try:
            # 调用LLM提取
            logger.info(f"开始提取金句: {source_title}")
            response = self._call_llm(safe_text, source_title)
            
            # 解析响应
            quotes_data = self._parse_json_response(response)
            
            if not quotes_data:
                logger.warning("未提取到有效金句")
                return []
            
            # 转换为Quote对象
            quotes = []
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for item in quotes_data:
                quote = Quote(
                    text=item.get('text', ''),
                    topic=item.get('topic', '其他'),
                    source_title=source_title,
                    source_author=source_author,
                    source_url=source_url,
                    platform=platform,
                    created_at=timestamp,
                    context=item.get('context', ''),
                    usage=item.get('usage', ''),
                )
                if quote.text:  # 只添加有内容的金句
                    quotes.append(quote)
            
            logger.info(f"提取到 {len(quotes)} 个金句")
            return quotes
            
        except Exception as e:
            logger.error(f"金句提取失败: {e}")
            return []
    
    def extract_from_file(
        self,
        file_path: str,
        source_title: Optional[str] = None,
        source_author: str = "",
        source_url: str = "",
        platform: str = ""
    ) -> List[Quote]:
        """从文件提取金句
        
        Args:
            file_path: 文件路径
            source_title: 来源标题（可选，默认使用文件名）
            source_author: 来源作者
            source_url: 原文链接
            platform: 平台名称
            
        Returns:
            List[Quote]: 金句列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if not source_title:
                source_title = Path(file_path).stem
            
            return self.extract(
                text=text,
                source_title=source_title,
                source_author=source_author,
                source_url=source_url,
                platform=platform,
            )
            
        except Exception as e:
            logger.error(f"从文件提取金句失败: {e}")
            return []


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='金句提取器')
    parser.add_argument('--text', '-t', help='要提取金句的文本')
    parser.add_argument('--file', '-f', help='从文件读取文本')
    parser.add_argument('--title', help='来源标题')
    parser.add_argument('--author', '-a', default='', help='来源作者')
    parser.add_argument('--url', '-u', default='', help='原文链接')
    parser.add_argument('--platform', '-p', default='', help='平台名称')
    parser.add_argument('--count', '-c', type=int, default=20, help='提取数量')
    parser.add_argument('--output', '-o', help='输出文件路径')
    
    args = parser.parse_args()
    
    # 获取文本
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
    elif args.text:
        text = args.text
    else:
        print("请提供 --text 或 --file 参数")
        return
    
    # 提取金句
    extractor = QuoteExtractor(quotes_per_video=args.count)
    quotes = extractor.extract(
        text=text,
        source_title=args.title or "未知来源",
        source_author=args.author,
        source_url=args.url,
        platform=args.platform,
    )
    
    # 输出结果
    if args.output:
        # 输出到文件
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(f"# 金句库 | {datetime.now().strftime('%Y-%m-%d')}\n\n")
            for i, quote in enumerate(quotes, 1):
                f.write(f"## {i}. {quote.topic}\n\n")
                f.write(quote.to_markdown() + "\n\n")
        print(f"已保存到: {args.output}")
    else:
        # 输出到控制台
        print(f"\n提取到 {len(quotes)} 个金句:\n")
        for i, quote in enumerate(quotes, 1):
            print(f"{i}. [{quote.topic}] {quote.text}")
            if quote.usage:
                print(f"   💡 {quote.usage}")
            print()


if __name__ == '__main__':
    main()
