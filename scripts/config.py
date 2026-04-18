#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库配置模块
集中管理所有知识库的同步配置
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 知识库同步配置
KNOWLEDGE_BASE_CONFIG = {
    # 飞书知识库配置
    "feishu": {
        "enabled": os.environ.get('FEISHU_ENABLED', 'false').lower() == 'true',
        "wiki_space": os.environ.get('FEISHU_WIKI_SPACE', 'my_library'),
        "root_folder": os.environ.get('FEISHU_ROOT_FOLDER', '内容监控'),
        "platform_folders": {
            "小宇宙": "小宇宙",
            "YouTube": "YouTube",
            "B站": "B站",
            "Twitter": "Twitter",
        },
    },
    
    # Obsidian 知识库配置
    "obsidian": {
        "enabled": os.environ.get('OBSIDIAN_ENABLED', 'false').lower() == 'true',
        "vault_path": os.environ.get('OBSIDIAN_VAULT_PATH', ''),
        "folder": os.environ.get('OBSIDIAN_FOLDER', '内容监控'),
        "add_frontmatter": os.environ.get('OBSIDIAN_FRONTMATTER', 'true').lower() == 'true',
        "file_naming": os.environ.get('OBSIDIAN_FILE_NAMING', 'date_title'),  # date_title | title_date
        "platform_folders": {
            "小宇宙": "小宇宙",
            "YouTube": "YouTube",
            "B站": "B站",
            "Twitter": "Twitter",
        },
    },
}

# 输出目录配置
OUTPUT_DIR = PROJECT_ROOT / "输出"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 平台输出子目录
PLATFORM_OUTPUT_DIRS = {
    "小宇宙": OUTPUT_DIR / "小宇宙",
    "YouTube": OUTPUT_DIR / "YouTube",
    "B站": OUTPUT_DIR / "B站",
    "Twitter": OUTPUT_DIR / "Twitter",
}

# 确保目录存在
for dir_path in PLATFORM_OUTPUT_DIRS.values():
    dir_path.mkdir(parents=True, exist_ok=True)


def get_enabled_knowledge_bases() -> List[str]:
    """获取已启用的知识库列表"""
    enabled = []
    for kb, config in KNOWLEDGE_BASE_CONFIG.items():
        if config.get('enabled', False):
            enabled.append(kb)
    return enabled


def validate_obsidian_config() -> tuple[bool, str]:
    """验证 Obsidian 配置是否正确
    
    Returns:
        (is_valid, error_message)
    """
    obsidian_config = KNOWLEDGE_BASE_CONFIG.get('obsidian', {})
    
    if not obsidian_config.get('enabled'):
        return True, ""
    
    vault_path = obsidian_config.get('vault_path', '')
    
    if not vault_path:
        return False, "OBSIDIAN_VAULT_PATH 未配置"
    
    vault_dir = Path(vault_path)
    
    if not vault_dir.exists():
        return False, f"Obsidian vault 路径不存在: {vault_path}"
    
    if not vault_dir.is_dir():
        return False, f"Obsidian vault 路径不是目录: {vault_path}"
    
    # 检查是否包含 .obsidian 配置文件（确认是 vault）
    obsidian_config_dir = vault_dir / ".obsidian"
    if not obsidian_config_dir.exists():
        return False, f"指定的路径不是有效的 Obsidian vault（缺少 .obsidian 配置目录）: {vault_path}"
    
    return True, ""


def validate_feishu_config() -> tuple[bool, str]:
    """验证飞书配置是否正确
    
    Returns:
        (is_valid, error_message)
    """
    feishu_config = KNOWLEDGE_BASE_CONFIG.get('feishu', {})
    
    if not feishu_config.get('enabled'):
        return True, ""
    
    # 检查 lark-cli 是否可用
    import subprocess
    try:
        result = subprocess.run(
            ['lark', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False, "lark-cli 未正确安装或配置"
    except FileNotFoundError:
        return False, "lark-cli 未安装（请参考 README.md 安装）"
    except Exception as e:
        return False, f"检查 lark-cli 时出错: {str(e)}"
    
    return True, ""


def validate_all_config() -> Dict[str, tuple[bool, str]]:
    """验证所有知识库配置
    
    Returns:
        {kb_name: (is_valid, error_message)}
    """
    results = {}
    
    for kb in KNOWLEDGE_BASE_CONFIG.keys():
        if kb == 'feishu':
            results[kb] = validate_feishu_config()
        elif kb == 'obsidian':
            results[kb] = validate_obsidian_config()
        else:
            results[kb] = (True, "")
    
    return results
