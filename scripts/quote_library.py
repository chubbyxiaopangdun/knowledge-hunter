#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
素材库管理模块 - 管理金句素材库
支持按主题/标签搜索、按时间排序、Markdown存储
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuoteLibrary:
    """素材库管理类
    
    管理金句素材库，支持：
    - 按主题/标签搜索
    - 按时间排序
    - Markdown格式存储
    - 元数据索引
    
    目录结构：
    ```
    quotes/
    ├── all_quotes.md          # 全部金句汇总
    ├── by_topic/              # 按主题分类
    │   ├── AI创业.md
    │   ├── 个人成长.md
    │   └── ...
    └── metadata.json          # 元数据索引
    ```
    """
    
    def __init__(self, base_dir: str = "./quotes"):
        """初始化素材库
        
        Args:
            base_dir: 素材库根目录
        """
        self.base_dir = Path(base_dir)
        self.by_topic_dir = self.base_dir / "by_topic"
        self.metadata_file = self.base_dir / "metadata.json"
        self.all_quotes_file = self.base_dir / "all_quotes.md"
        
        # 创建目录结构
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保目录结构存在"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.by_topic_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_metadata(self) -> Dict:
        """加载元数据"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载元数据失败: {e}")
        return {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'total_quotes': 0,
            'topics': {},
            'sources': {},
            'last_updated': None,
        }
    
    def _save_metadata(self, metadata: Dict):
        """保存元数据"""
        metadata['last_updated'] = datetime.now().isoformat()
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存元数据失败: {e}")
    
    def _normalize_topic(self, topic: str) -> str:
        """标准化主题名称（用于文件名）"""
        # 替换特殊字符
        topic = topic.strip()
        topic = topic.replace('/', '-').replace('\\', '-')
        topic = topic.replace('*', '').replace('?', '')
        topic = topic.replace(':', '-').replace('|', '-')
        # 限制长度
        if len(topic) > 30:
            topic = topic[:30]
        return topic
    
    def _get_topic_file(self, topic: str) -> Path:
        """获取主题文件路径"""
        filename = self._normalize_topic(topic) + ".md"
        return self.by_topic_dir / filename
    
    def _extract_topics_from_text(self, text: str) -> List[str]:
        """从文本中提取主题关键词"""
        common_topics = [
            "AI", "人工智能", "创业", "投资", "职场", "技术", "产品",
            "运营", "增长", "管理", "营销", "品牌", "人生", "成长",
            "情感", "健康", "生活", "商业", "趋势", "自媒体",
            "短视频", "直播", "电商", "私域", "流量", "变现",
            "认知", "思维", "格局", "执行力", "领导力"
        ]
        
        found_topics = []
        text_lower = text.lower()
        
        for topic in common_topics:
            if topic.lower() in text_lower:
                found_topics.append(topic)
        
        return found_topics if found_topics else ["其他"]
    
    def add_quote(self, quote: 'Quote'):
        """添加单个金句
        
        Args:
            quote: Quote对象
        """
        self.add_quotes([quote])
    
    def add_quotes(self, quotes: List['Quote']):
        """批量添加金句
        
        Args:
            quotes: Quote对象列表
        """
        if not quotes:
            return
        
        metadata = self._load_metadata()
        
        # 按主题分组
        topic_groups = defaultdict(list)
        for quote in quotes:
            topic_groups[quote.topic].append(quote)
        
        # 更新元数据
        metadata['total_quotes'] = metadata.get('total_quotes', 0) + len(quotes)
        
        # 更新各主题文件
        for topic, topic_quotes in topic_groups.items():
            self._update_topic_file(topic, topic_quotes, metadata)
        
        # 更新全部金句文件
        self._update_all_quotes_file(quotes)
        
        # 保存元数据
        self._save_metadata(metadata)
        
        logger.info(f"已添加 {len(quotes)} 个金句到素材库")
    
    def _update_topic_file(self, topic: str, quotes: List['Quote'], metadata: Dict):
        """更新主题文件"""
        file_path = self._get_topic_file(topic)
        
        # 获取现有内容
        existing_content = ""
        if file_path.exists():
            existing_content = file_path.read_text(encoding='utf-8')
        
        # 构建新内容
        lines = []
        
        # 检查是否需要添加头部
        if not existing_content.startswith('#'):
            lines.append(f"# {topic}\n")
            lines.append(f"> 本文件收集自创作者金句素材库 | 自动生成\n")
            lines.append("")
        
        # 添加新金句
        for quote in quotes:
            quote_block = [
                f"## {quote.source_title}",
                "",
                f"> {quote.text}",
                "",
                f"- **作者**: {quote.source_author or '未知'}",
                f"- **平台**: {quote.platform or '未知'}",
                f"- **类型**: {quote.topic}",
                f"- **时间**: {quote.created_at}",
            ]
            if quote.source_url:
                quote_block.append(f"- **链接**: {quote.source_url}")
            if quote.usage:
                quote_block.append(f"- **使用建议**: {quote.usage}")
            
            lines.extend(quote_block)
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # 追加到现有内容
        content = existing_content.strip() + "\n\n" + "\n".join(lines)
        
        # 写入文件
        file_path.write_text(content, encoding='utf-8')
        
        # 更新元数据
        if topic not in metadata['topics']:
            metadata['topics'][topic] = {
                'count': 0,
                'file': str(file_path.name),
                'created_at': datetime.now().isoformat(),
            }
        metadata['topics'][topic]['count'] = metadata['topics'][topic].get('count', 0) + len(quotes)
        
        logger.debug(f"已更新主题文件: {file_path.name}")
    
    def _update_all_quotes_file(self, new_quotes: List['Quote']):
        """更新全部金句汇总文件"""
        lines = [
            f"# 全部金句",
            "",
            f"> 共 **{len(new_quotes)}** 个金句 | 更新于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            "",
        ]
        
        for quote in new_quotes:
            quote_block = [
                f"## {quote.source_title}",
                "",
                f"> {quote.text}",
                "",
                f"- **主题**: {quote.topic}",
                f"- **作者**: {quote.source_author or '未知'}",
                f"- **平台**: {quote.platform or '未知'}",
                f"- **时间**: {quote.created_at}",
            ]
            if quote.source_url:
                quote_block.append(f"- **链接**: {quote.source_url}")
            if quote.usage:
                quote_block.append(f"- **使用建议**: {quote.usage}")
            
            lines.extend(quote_block)
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # 追加到现有内容
        existing_content = ""
        if self.all_quotes_file.exists():
            existing_content = self.all_quotes_file.read_text(encoding='utf-8')
        
        content = "\n".join(lines) + "\n\n" + existing_content
        
        self.all_quotes_file.write_text(content, encoding='utf-8')
    
    def search_by_topic(self, topic: str) -> List[Dict]:
        """按主题搜索金句
        
        Args:
            topic: 主题关键词
            
        Returns:
            匹配的金句列表
        """
        file_path = self._get_topic_file(topic)
        
        if not file_path.exists():
            # 尝试模糊匹配
            matching_files = []
            for f in self.by_topic_dir.glob("*.md"):
                if topic.lower() in f.stem.lower():
                    matching_files.append(f)
            
            if not matching_files:
                logger.info(f"未找到主题 '{topic}' 的金句")
                return []
            
            results = []
            for f in matching_files:
                results.extend(self._parse_quotes_from_file(f))
            return results
        
        return self._parse_quotes_from_file(file_path)
    
    def _parse_quotes_from_file(self, file_path: Path) -> List[Dict]:
        """从文件解析金句"""
        content = file_path.read_text(encoding='utf-8')
        
        quotes = []
        # 简单的Markdown解析
        import re
        blocks = re.split(r'---', content)
        
        for block in blocks:
            if '> ' in block:
                # 提取金句
                text_match = re.search(r'> (.+)', block)
                if text_match:
                    quote = {
                        'text': text_match.group(1).strip(),
                        'topic': file_path.stem,
                        'source_title': '',
                        'created_at': '',
                    }
                    
                    # 提取其他信息
                    if '**作者**:' in block:
                        author_match = re.search(r'\*\*作者\*\*: (.+)', block)
                        if author_match:
                            quote['author'] = author_match.group(1).strip()
                    
                    if '**平台**:' in block:
                        platform_match = re.search(r'\*\*平台\*\*: (.+)', block)
                        if platform_match:
                            quote['platform'] = platform_match.group(1).strip()
                    
                    if '**链接**:' in block:
                        url_match = re.search(r'\*\*链接\*\*: (.+)', block)
                        if url_match:
                            quote['source_url'] = url_match.group(1).strip()
                    
                    quotes.append(quote)
        
        return quotes
    
    def search_by_keyword(self, keyword: str) -> List[Dict]:
        """按关键词搜索金句
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的金句列表
        """
        results = []
        keyword_lower = keyword.lower()
        
        # 搜索所有主题文件
        for topic_file in self.by_topic_dir.glob("*.md"):
            content = topic_file.read_text(encoding='utf-8')
            if keyword_lower in content.lower():
                # 提取匹配的金句
                matches = self._search_in_content(content, keyword_lower, topic_file.stem)
                results.extend(matches)
        
        return results
    
    def _search_in_content(self, content: str, keyword: str, topic: str) -> List[Dict]:
        """在内容中搜索"""
        import re
        results = []
        
        blocks = re.split(r'---', content)
        for block in blocks:
            if keyword in block.lower() and '> ' in block:
                text_match = re.search(r'> (.+)', block)
                if text_match:
                    results.append({
                        'text': text_match.group(1).strip(),
                        'topic': topic,
                        'matched_on': 'keyword',
                    })
        
        return results
    
    def get_all_topics(self) -> List[Tuple[str, int]]:
        """获取所有主题及其金句数量
        
        Returns:
            [(主题名, 数量), ...]
        """
        metadata = self._load_metadata()
        topics = metadata.get('topics', {})
        
        return [(topic, data.get('count', 0)) for topic, data in topics.items()]
    
    def get_recent_quotes(self, limit: int = 50) -> List[Dict]:
        """获取最近添加的金句
        
        Args:
            limit: 返回数量限制
            
        Returns:
            金句列表
        """
        metadata = self._load_metadata()
        total = metadata.get('total_quotes', 0)
        
        if total == 0:
            return []
        
        # 读取全部金句文件获取最新内容
        if not self.all_quotes_file.exists():
            return []
        
        content = self.all_quotes_file.read_text(encoding='utf-8')
        return self._parse_recent_quotes(content, limit)
    
    def _parse_recent_quotes(self, content: str, limit: int) -> List[Dict]:
        """解析最近的金句"""
        import re
        results = []
        
        blocks = re.split(r'---', content)
        for block in blocks:
            if '> ' in block and len(results) < limit:
                text_match = re.search(r'> (.+)', block)
                if text_match:
                    quote = {
                        'text': text_match.group(1).strip(),
                        'topic': '',
                    }
                    
                    # 提取主题
                    if '**主题**:' in block:
                        topic_match = re.search(r'\*\*主题\*\*: (.+)', block)
                        if topic_match:
                            quote['topic'] = topic_match.group(1).strip()
                    
                    if '**作者**:' in block:
                        author_match = re.search(r'\*\*作者\*\*: (.+)', block)
                        if author_match:
                            quote['author'] = author_match.group(1).strip()
                    
                    results.append(quote)
        
        return results
    
    def get_statistics(self) -> Dict:
        """获取素材库统计信息
        
        Returns:
            统计信息字典
        """
        metadata = self._load_metadata()
        
        return {
            'total_quotes': metadata.get('total_quotes', 0),
            'total_topics': len(metadata.get('topics', {})),
            'last_updated': metadata.get('last_updated'),
            'topics': metadata.get('topics', {}),
        }
    
    def export_to_markdown(self, output_path: Optional[str] = None) -> str:
        """导出全部金句为Markdown
        
        Args:
            output_path: 输出文件路径（可选）
            
        Returns:
            Markdown内容
        """
        metadata = self._load_metadata()
        topics = metadata.get('topics', {})
        
        lines = [
            f"# 金句素材库",
            "",
            f"> 共 {metadata.get('total_quotes', 0)} 个金句 | 涵盖 {len(topics)} 个主题",
            "",
            f"最后更新: {metadata.get('last_updated', '未知')}",
            "",
            "---",
            "",
            "## 📚 主题索引",
            "",
        ]
        
        # 添加主题索引
        for topic, data in sorted(topics.items(), key=lambda x: x[1].get('count', 0), reverse=True):
            count = data.get('count', 0)
            lines.append(f"- [{topic}](#{topic.lower()}) ({count}个)")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 添加各主题内容
        for topic in sorted(topics.keys()):
            file_path = self._get_topic_file(topic)
            if file_path.exists():
                lines.append(f"## {topic}\n")
                content = file_path.read_text(encoding='utf-8')
                # 移除头部（避免重复）
                if content.startswith('#'):
                    content = re.sub(r'^#.*\n', '', content, count=1)
                if '> 本文件收集' in content:
                    content = re.sub(r'> 本文件收集.*\n', '', content)
                lines.append(content)
                lines.append("")
        
        markdown = '\n'.join(lines)
        
        if output_path:
            Path(output_path).write_text(markdown, encoding='utf-8')
            logger.info(f"已导出到: {output_path}")
        
        return markdown
    
    def search(
        self,
        keyword: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """综合搜索
        
        Args:
            keyword: 关键词搜索
            topic: 主题筛选
            limit: 返回数量限制
            
        Returns:
            匹配的金句列表
        """
        if topic:
            results = self.search_by_topic(topic)
        elif keyword:
            results = self.search_by_keyword(keyword)
        else:
            results = self.get_recent_quotes(limit)
        
        return results[:limit]


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='素材库管理工具')
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # 统计命令
    subparsers.add_parser('stats', help='查看统计信息')
    
    # 列表命令
    list_parser = subparsers.add_parser('list', help='列出金句')
    list_parser.add_argument('--topic', '-t', help='按主题筛选')
    list_parser.add_argument('--limit', '-l', type=int, default=20, help='数量限制')
    
    # 搜索命令
    search_parser = subparsers.add_parser('search', help='搜索金句')
    search_parser.add_argument('keyword', help='搜索关键词')
    search_parser.add_argument('--limit', '-l', type=int, default=20, help='数量限制')
    
    # 导出命令
    export_parser = subparsers.add_parser('export', help='导出素材库')
    export_parser.add_argument('--output', '-o', default='quotes_export.md', help='输出文件')
    
    args = parser.parse_args()
    
    library = QuoteLibrary()
    
    if args.command == 'stats':
        stats = library.get_statistics()
        print(f"\n📊 素材库统计")
        print(f"- 总金句数: {stats['total_quotes']}")
        print(f"- 主题数: {stats['total_topics']}")
        print(f"- 最后更新: {stats['last_updated'] or '未知'}")
        print(f"\n📚 主题分布:")
        for topic, data in sorted(stats['topics'].items(), key=lambda x: x[1].get('count', 0), reverse=True):
            print(f"  - {topic}: {data.get('count', 0)} 个")
    
    elif args.command == 'list':
        if args.topic:
            quotes = library.search_by_topic(args.topic)
        else:
            quotes = library.get_recent_quotes(args.limit)
        
        print(f"\n📝 金句列表 (共 {len(quotes)} 个)\n")
        for i, quote in enumerate(quotes, 1):
            print(f"{i}. [{quote.get('topic', '未知')}] {quote.get('text', '')}")
    
    elif args.command == 'search':
        quotes = library.search_by_keyword(args.keyword)
        print(f"\n🔍 搜索结果: '{args.keyword}' (共 {len(quotes)} 个)\n")
        for i, quote in enumerate(quotes[:args.limit], 1):
            print(f"{i}. [{quote.get('topic', '未知')}] {quote.get('text', '')}")
    
    elif args.command == 'export':
        library.export_to_markdown(args.output)
        print(f"✅ 已导出到: {args.output}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
