#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库同步器基类和工厂
支持多知识库同步（飞书、Obsidian等）
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List

from config import KNOWLEDGE_BASE_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeBaseSyncer(ABC):
    """知识库同步器基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """同步器名称"""
        pass
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台标识名（用于日志等）"""
        pass
    
    @abstractmethod
    def sync(self, file_path: Path, platform: str) -> bool:
        """同步单个文件
        
        Args:
            file_path: 文件路径
            platform: 平台名称（如 小宇宙、YouTube）
            
        Returns:
            bool: 同步是否成功
        """
        pass
    
    @abstractmethod
    def sync_batch(self, files: Dict[str, List[Path]]) -> Dict[str, int]:
        """批量同步
        
        Args:
            files: 待同步文件字典 {platform: [file_paths]}
            
        Returns:
            Dict[str, int]: 同步结果 {"success": count, "failed": count, "skipped": count}
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> tuple[bool, str]:
        """验证配置是否正确
        
        Returns:
            (is_valid, error_message)
        """
        pass


class KnowledgeBaseFactory:
    """知识库工厂 - 根据配置创建同步器"""
    
    _syncers: List[KnowledgeBaseSyncer] = []
    _initialized: bool = False
    
    @classmethod
    def create_syncers(cls) -> List[KnowledgeBaseSyncer]:
        """根据配置创建所有启用的同步器
        
        Returns:
            List[KnowledgeBaseSyncer]: 同步器列表
        """
        if cls._initialized:
            return cls._syncers
        
        cls._syncers = []
        config = KNOWLEDGE_BASE_CONFIG
        
        # 创建飞书同步器
        feishu_config = config.get('feishu', {})
        if feishu_config.get('enabled'):
            try:
                from sync_to_feishu import FeishuSyncer
                syncer = FeishuSyncer(config=feishu_config)
                is_valid, error = syncer.validate_config()
                if is_valid:
                    cls._syncers.append(syncer)
                    logger.info(f"已加载飞书同步器")
                else:
                    logger.warning(f"飞书同步器配置无效: {error}")
            except ImportError as e:
                logger.warning(f"无法导入飞书同步器: {e}")
        
        # 创建 Obsidian 同步器
        obsidian_config = config.get('obsidian', {})
        if obsidian_config.get('enabled'):
            try:
                from sync_to_obsidian import ObsidianSyncer
                syncer = ObsidianSyncer(config=obsidian_config)
                is_valid, error = syncer.validate_config()
                if is_valid:
                    cls._syncers.append(syncer)
                    logger.info(f"已加载 Obsidian 同步器")
                else:
                    logger.warning(f"Obsidian 同步器配置无效: {error}")
            except ImportError as e:
                logger.warning(f"无法导入 Obsidian 同步器: {e}")
        
        cls._initialized = True
        logger.info(f"知识库同步器初始化完成，共 {len(cls._syncers)} 个")
        
        return cls._syncers
    
    @classmethod
    def get_syncer(cls, name: str) -> KnowledgeBaseSyncer | None:
        """获取指定名称的同步器
        
        Args:
            name: 同步器名称（如 'feishu', 'obsidian'）
            
        Returns:
            KnowledgeBaseSyncer | None
        """
        if not cls._initialized:
            cls.create_syncers()
        
        for syncer in cls._syncers:
            if syncer.name == name:
                return syncer
        
        return None
    
    @classmethod
    def sync_all(cls, files: Dict[str, List[Path]]) -> Dict[str, Dict[str, int]]:
        """同步到所有启用的知识库
        
        Args:
            files: 待同步文件字典 {platform: [file_paths]}
            
        Returns:
            Dict[str, Dict[str, int]]: 各知识库的同步结果
        """
        if not cls._initialized:
            cls.create_syncers()
        
        results = {}
        
        for syncer in cls._syncers:
            syncer_name = syncer.name
            logger.info(f"开始同步到 {syncer_name}...")
            
            try:
                result = syncer.sync_batch(files)
                results[syncer_name] = result
                logger.info(f"{syncer_name} 同步完成: 成功 {result.get('success', 0)}, 失败 {result.get('failed', 0)}")
            except Exception as e:
                logger.error(f"{syncer_name} 同步失败: {e}")
                results[syncer_name] = {'success': 0, 'failed': 0, 'error': str(e)}
        
        return results
    
    @classmethod
    def reset(cls):
        """重置同步器缓存（用于重新加载配置）"""
        cls._syncers = []
        cls._initialized = False
