#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识猎手 - 错误通知模块
支持多种通知渠道：日志、飞书、邮件、Webhook
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ErrorNotifier:
    """错误通知器
    
    支持多种通知方式：
    1. 日志记录（默认）
    2. 飞书机器人
    3. 自定义Webhook
    4. 本地文件记录
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化通知器
        
        Args:
            config: 通知配置
                - feishu_webhook: 飞书机器人webhook地址
                - custom_webhook: 自定义webhook地址
                - error_log: 错误日志文件路径
        """
        self.config = config or {}
        self.error_log = self.config.get('error_log', './内容监控/日志/错误日志.json')
        
        # 确保日志目录存在
        Path(self.error_log).parent.mkdir(parents=True, exist_ok=True)
    
    def notify(self, 
               level: str,
               title: str,
               message: str,
               details: Optional[Dict] = None,
               channels: Optional[List[str]] = None):
        """发送通知
        
        Args:
            level: 通知级别 (info/warning/error/critical)
            title: 通知标题
            message: 通知内容
            details: 详细信息
            channels: 通知渠道列表，默认所有可用渠道
        """
        notification = {
            'level': level,
            'title': title,
            'message': message,
            'details': details or {},
            'timestamp': datetime.now().isoformat(),
        }
        
        channels = channels or ['log', 'file']
        
        for channel in channels:
            try:
                if channel == 'log':
                    self._notify_log(notification)
                elif channel == 'file':
                    self._notify_file(notification)
                elif channel == 'feishu':
                    self._notify_feishu(notification)
                elif channel == 'webhook':
                    self._notify_webhook(notification)
            except Exception as e:
                logger.error(f"通知发送失败 [{channel}]: {e}")
    
    def _notify_log(self, notification: Dict):
        """日志记录"""
        level = notification['level']
        title = notification['title']
        message = notification['message']
        
        log_msg = f"[{level.upper()}] {title}: {message}"
        
        if level == 'critical':
            logger.critical(log_msg)
        elif level == 'error':
            logger.error(log_msg)
        elif level == 'warning':
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
    
    def _notify_file(self, notification: Dict):
        """写入错误日志文件"""
        # 读取现有日志
        logs = []
        if Path(self.error_log).exists():
            try:
                with open(self.error_log, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except:
                logs = []
        
        # 添加新记录
        logs.append(notification)
        
        # 只保留最近100条
        logs = logs[-100:]
        
        # 保存
        with open(self.error_log, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    
    def _notify_feishu(self, notification: Dict):
        """发送飞书通知（使用Webhook）"""
        webhook_url = self.config.get('feishu_webhook') or os.environ.get('FEISHU_WEBHOOK')
        
        if not webhook_url:
            logger.warning("未配置飞书Webhook，跳过飞书通知")
            return
        
        try:
            import httpx
            
            # 构建飞书消息卡片
            level_emoji = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'error': '❌',
                'critical': '🔴',
            }
            
            level_color = {
                'info': 'blue',
                'warning': 'yellow',
                'error': 'red',
                'critical': 'red',
            }
            
            emoji = level_emoji.get(notification['level'], 'ℹ️')
            color = level_color.get(notification['level'], 'blue')
            
            payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"{emoji} 知识猎手 - {notification['title']}"
                        },
                        "template": color
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "plain_text",
                                "content": notification['message']
                            }
                        },
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"**时间**: {notification['timestamp']}"
                            }
                        }
                    ]
                }
            }
            
            with httpx.Client() as client:
                response = client.post(webhook_url, json=payload, timeout=10)
                if response.status_code == 200:
                    logger.info("飞书通知发送成功")
                else:
                    logger.warning(f"飞书通知发送失败: {response.text}")
                    
        except ImportError:
            logger.warning("未安装 httpx，无法发送飞书通知")
        except Exception as e:
            logger.error(f"飞书通知发送异常: {e}")
    
    def _notify_webhook(self, notification: Dict):
        """发送自定义Webhook通知"""
        webhook_url = self.config.get('custom_webhook') or os.environ.get('NOTIFICATION_WEBHOOK')
        
        if not webhook_url:
            logger.warning("未配置自定义Webhook，跳过")
            return
        
        try:
            import httpx
            
            with httpx.Client() as client:
                response = client.post(webhook_url, json=notification, timeout=10)
                if response.status_code == 200:
                    logger.info("Webhook通知发送成功")
                else:
                    logger.warning(f"Webhook通知发送失败: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Webhook通知发送异常: {e}")
    
    # 便捷方法
    def info(self, title: str, message: str, **kwargs):
        """发送信息通知"""
        self.notify('info', title, message, **kwargs)
    
    def warning(self, title: str, message: str, **kwargs):
        """发送警告通知"""
        self.notify('warning', title, message, **kwargs)
    
    def error(self, title: str, message: str, **kwargs):
        """发送错误通知"""
        self.notify('error', title, message, **kwargs)
    
    def critical(self, title: str, message: str, **kwargs):
        """发送严重错误通知"""
        self.notify('critical', title, message, **kwargs)
    
    def transcription_failed(self, platform: str, url: str, error: str):
        """转录失败通知"""
        self.error(
            title="转录失败",
            message=f"平台: {platform}, 链接: {url}",
            details={
                'platform': platform,
                'url': url,
                'error': error,
                'type': 'transcription_failed'
            },
            channels=['log', 'file', 'feishu']
        )
    
    def download_failed(self, platform: str, url: str, error: str):
        """下载失败通知"""
        self.error(
            title="下载失败",
            message=f"平台: {platform}, 无法下载内容",
            details={
                'platform': platform,
                'url': url,
                'error': error,
                'type': 'download_failed'
            },
            channels=['log', 'file']
        )
    
    def sync_failed(self, platform: str, file_path: str, error: str):
        """同步失败通知"""
        self.warning(
            title="同步失败",
            message=f"平台: {platform}, 文件同步到飞书失败",
            details={
                'platform': platform,
                'file': file_path,
                'error': error,
                'type': 'sync_failed'
            },
            channels=['log', 'file']
        )


# 全局通知器实例
_notifier: Optional[ErrorNotifier] = None


def get_notifier(config: Optional[Dict] = None) -> ErrorNotifier:
    """获取全局通知器实例"""
    global _notifier
    if _notifier is None:
        _notifier = ErrorNotifier(config)
    return _notifier


def notify_error(title: str, message: str, **kwargs):
    """便捷方法：发送错误通知"""
    get_notifier().error(title, message, **kwargs)


def notify_warning(title: str, message: str, **kwargs):
    """便捷方法：发送警告通知"""
    get_notifier().warning(title, message, **kwargs)


def notify_info(title: str, message: str, **kwargs):
    """便捷方法：发送信息通知"""
    get_notifier().info(title, message, **kwargs)
