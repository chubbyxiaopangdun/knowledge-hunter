#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian 同步模块
将转录内容同步到 Obsidian vault
支持 frontmatter 和双链语法
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ObsidianSyncer:
    """Obsidian 同步器"""
    
    def __init__(self, config: Dict = None):
        """初始化 Obsidian 同步器
        
        Args:
            config: Obsidian 配置
        """
        if config is None:
            config = {}
        
        self.vault_path = config.get('vault_path', os.environ.get('OBSIDIAN_VAULT_PATH', ''))
        self.folder = config.get('folder', '内容监控')
        self.add_frontmatter = config.get('add_frontmatter', True)
        self.file_naming = config.get('file_naming', 'date_title')
        self.platform_folders = config.get('platform_folders', {
            "小宇宙": "小宇宙",
            "YouTube": "YouTube",
            "B站": "B站",
            "Twitter": "Twitter",
        })
        
        # 计算目标目录
        self.target_dir = Path(self.vault_path) / self.folder if self.vault_path else None
        
        self._name = "obsidian"
    
    @property
    def name(self) -> str:
        """同步器名称"""
        return self._name
    
    @property
    def platform_name(self) -> str:
        """平台标识名"""
        return "Obsidian"
    
    def validate_config(self) -> tuple[bool, str]:
        """验证配置是否正确
        
        Returns:
            (is_valid, error_message)
        """
        if not self.vault_path:
            return False, "OBSIDIAN_VAULT_PATH 未配置"
        
        vault_dir = Path(self.vault_path)
        
        if not vault_dir.exists():
            return False, f"Obsidian vault 路径不存在: {self.vault_path}"
        
        if not vault_dir.is_dir():
            return False, f"Obsidian vault 路径不是目录: {self.vault_path}"
        
        # 检查是否包含 .obsidian 配置文件
        obsidian_config_dir = vault_dir / ".obsidian"
        if not obsidian_config_dir.exists():
            return False, f"指定的路径不是有效的 Obsidian vault（缺少 .obsidian 配置目录）"
        
        return True, ""
    
    def _get_platform_folder(self, platform: str) -> Path:
        """获取平台对应的文件夹路径
        
        Args:
            platform: 平台名称
            
        Returns:
            Path: 文件夹路径
        """
        folder_name = self.platform_folders.get(platform, platform)
        return self.target_dir / folder_name
    
    def _generate_frontmatter(
        self,
        file_path: Path,
        platform: str,
        original_content: str
    ) -> str:
        """生成 Obsidian frontmatter
        
        Args:
            file_path: 原文件路径
            platform: 平台名称
            original_content: 原始内容
            
        Returns:
            str: 包含 frontmatter 的内容
        """
        # 提取标题（第一个 # 开头的行）
        title = file_path.stem
        lines = original_content.split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#') and stripped[1:].strip():
                title = stripped.lstrip('#').strip()
                break
        
        # 提取标签（从内容中的 #话题 格式）
        tags = set()
        tags.add(platform)  # 添加平台标签
        
        # 从文件名和标题中提取标签
        tag_pattern = re.compile(r'#([\w\u4e00-\u9fa5]+)')
        for match in tag_pattern.finditer(original_content[:500]):  # 只检查前500字
            tag = match.group(1)
            if len(tag) < 10 and not tag.isdigit():  # 过滤太长的标签
                tags.add(tag)
        
        # 平台特定标签
        platform_tags = {
            "小宇宙": ["播客", "转录"],
            "YouTube": ["视频", "转录"],
            "B站": ["视频", "转录"],
            "Twitter": ["推文"],
        }
        if platform in platform_tags:
            tags.update(platform_tags[platform])
        
        # 生成 frontmatter
        today = datetime.now().strftime('%Y-%m-%d')
        
        frontmatter = f"""---
date: {today}
source: {platform}
tags: [{', '.join(sorted(tags))}]
status: new
---

"""
        
        return frontmatter + original_content
    
    def _process_double_links(self, content: str) -> str:
        """处理 Obsidian 双链语法
        
        将 [[话题]] 格式的内容保持原样（Obsidian 原生支持）
        并尝试补全不完整的链接
        
        Args:
            content: 原始内容
            
        Returns:
            str: 处理后的内容
        """
        # 验证已有的双链格式
        double_link_pattern = re.compile(r'\[\[([^\]]+)\]\]')
        
        def expand_link(match):
            link_text = match.group(1)
            # 如果链接中包含 |，保留别名部分
            if '|' in link_text:
                return match.group(0)
            # 否则保持原样，让 Obsidian 自动处理
            return match.group(0)
        
        return double_link_pattern.sub(expand_link, content)
    
    def _generate_filename(self, file_path: Path, platform: str) -> str:
        """生成 Obsidian 文件名
        
        Args:
            file_path: 原文件路径
            platform: 平台名称
            
        Returns:
            str: 新的文件名
        """
        today = datetime.now().strftime('%Y-%m-%d')
        title = file_path.stem
        
        # 清理文件名（移除不合法字符）
        title = re.sub(r'[<>:"/\\|?*]', '_', title)
        title = title[:100]  # 限制长度
        
        if self.file_naming == 'date_title':
            return f"{today}_{title}.md"
        else:
            return f"{title}_{today}.md"
    
    def _ensure_directories(self, platform: str) -> bool:
        """确保目录存在
        
        Args:
            platform: 平台名称
            
        Returns:
            bool: 是否成功
        """
        try:
            folder_path = self._get_platform_folder(platform)
            folder_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            return False
    
    def sync(self, file_path: Path, platform: str) -> bool:
        """同步单个文件
        
        Args:
            file_path: 文件路径
            platform: 平台名称
            
        Returns:
            bool: 同步是否成功
        """
        try:
            # 验证目标目录
            if not self.validate_config()[0]:
                logger.error("Obsidian 配置无效")
                return False
            
            # 确保目录存在
            if not self._ensure_directories(platform):
                return False
            
            # 读取原始内容
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 处理内容
            content = original_content
            if self.add_frontmatter:
                content = self._generate_frontmatter(file_path, platform, content)
            
            content = self._process_double_links(content)
            
            # 生成新文件名
            new_filename = self._generate_filename(file_path, platform)
            target_path = self._get_platform_folder(platform) / new_filename
            
            # 写入文件
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"已同步到 Obsidian: {target_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"同步文件失败 {file_path}: {e}")
            return False
    
    def sync_batch(self, files: Dict[str, List[Path]]) -> Dict[str, int]:
        """批量同步
        
        Args:
            files: 待同步文件字典 {platform: [file_paths]}
            
        Returns:
            Dict[str, int]: 同步结果
        """
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
        }
        
        total_files = sum(len(file_list) for file_list in files.values())
        
        if total_files == 0:
            logger.info("没有待同步的文件")
            return results
        
        # 验证配置
        is_valid, error = self.validate_config()
        if not is_valid:
            logger.error(f"Obsidian 配置无效: {error}")
            results['failed'] = total_files
            return results
        
        logger.info(f"开始同步到 Obsidian，共 {total_files} 个文件")
        
        for platform, file_list in files.items():
            logger.info(f"处理平台: {platform} ({len(file_list)} 个文件)")
            
            for file_path in file_list:
                if self.sync(file_path, platform):
                    results['success'] += 1
                else:
                    results['failed'] += 1
        
        return results
    
    def get_pending_files(self) -> Dict[str, List[Path]]:
        """获取待同步的文件（从输出目录）"""
        from config import PLATFORM_OUTPUT_DIRS
        
        pending = {}
        
        for platform, platform_dir in PLATFORM_OUTPUT_DIRS.items():
            if not platform_dir.exists():
                continue
            
            files = list(platform_dir.glob("*.md"))
            
            if files:
                pending[platform] = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
        
        return pending
    
    def generate_report(self, results: Dict) -> str:
        """生成同步报告
        
        Args:
            results: 同步结果
            
        Returns:
            str: 报告内容
        """
        lines = []
        lines.append(f"# Obsidian 同步报告\n")
        lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"> Vault: {self.vault_path}\n")
        lines.append(f"> 目标文件夹: {self.folder}\n")
        lines.append("\n---\n\n")
        
        lines.append(f"## 同步结果汇总\n\n")
        lines.append(f"- ✅ 成功: {results.get('success', 0)} 个\n")
        lines.append(f"- ❌ 失败: {results.get('failed', 0)} 个\n")
        lines.append(f"- ⏭️ 跳过: {results.get('skipped', 0)} 个\n")
        
        return ''.join(lines)
