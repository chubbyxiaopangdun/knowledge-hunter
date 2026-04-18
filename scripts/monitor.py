#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容监控系统 - 主监控脚本
定时检查各平台更新并转录
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 添加脚本目录到路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# 配置日志
LOG_DIR = SCRIPT_DIR.parent / "日志"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / f"monitor_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger(__name__)


class ContentMonitor:
    """内容监控系统主类"""
    
    def __init__(self, enable_viewpoint: bool = True):
        """初始化监控系统
        
        Args:
            enable_viewpoint: 是否启用观点提取功能
        """
        self.start_time = datetime.now()
        self.config_path = SCRIPT_DIR.parent / "配置" / "博主列表.md"
        self.output_dir = SCRIPT_DIR.parent / "输出"
        self.enable_viewpoint = enable_viewpoint
        
        self.results = {
            'xiaoyuzhou': [],
            'youtube': [],
            'bilibili': [],
            'twitter': [],
            'feishu': {},
            'viewpoints': [],  # 新增：观点提取结果
        }
        
        # 观点提取器（按需初始化）
        self._viewpoint_extractor = None
        self._viewpoint_cache_dir = SCRIPT_DIR.parent / "缓存" / "观点库"
        
        # 检查配置
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}")
            logger.info("请先编辑配置文件添加博主")
    
    def check_dependencies(self) -> bool:
        """检查依赖是否安装"""
        required = ['whisper', 'yt_dlp', 'feedparser', 'httpx']
        missing = []
        
        for package in required:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        if missing:
            logger.error(f"缺少依赖包: {', '.join(missing)}")
            logger.info("请运行: pip install " + " ".join(missing))
            logger.info("或运行: bash setup.sh")
            return False
        
        return True
    
    def run_xiaoyuzhou(self) -> List[str]:
        """运行小宇宙监控"""
        logger.info("=" * 50)
        logger.info("开始检查小宇宙播客")
        
        try:
            from xiaoyuzhou import XiaoyuzhouMonitor
            monitor = XiaoyuzhouMonitor()
            results = monitor.run()
            logger.info(f"小宇宙处理完成: {len(results)} 个")
            return results
        except Exception as e:
            logger.error(f"小宇宙监控失败: {e}")
            return []
    
    def run_youtube(self) -> List[str]:
        """运行YouTube监控"""
        logger.info("=" * 50)
        logger.info("开始检查YouTube频道")
        
        try:
            from youtube import YouTubeMonitor
            monitor = YouTubeMonitor()
            results = monitor.run()
            logger.info(f"YouTube处理完成: {len(results)} 个")
            return results
        except Exception as e:
            logger.error(f"YouTube监控失败: {e}")
            return []
    
    def run_bilibili(self) -> List[str]:
        """运行B站监控"""
        logger.info("=" * 50)
        logger.info("开始检查B站UP主")
        
        try:
            from bilibili import BilibiliMonitor
            monitor = BilibiliMonitor()
            results = monitor.run()
            logger.info(f"B站处理完成: {len(results)} 个")
            return results
        except Exception as e:
            logger.error(f"B站监控失败: {e}")
            return []
    
    def run_twitter(self) -> List[str]:
        """运行Twitter监控"""
        logger.info("=" * 50)
        logger.info("开始检查Twitter账号")
        
        try:
            from twitter import TwitterMonitor
            monitor = TwitterMonitor()
            results = monitor.run()
            logger.info(f"Twitter处理完成: {len(results)} 个")
            return results
        except Exception as e:
            logger.error(f"Twitter监控失败: {e}")
            return []
    
    def run_feishu_sync(self, files: List[str]) -> Dict:
        """运行飞书同步"""
        logger.info("=" * 50)
        logger.info("开始同步到飞书")
        
        try:
            from sync_to_feishu import FeishuSyncer
            syncer = FeishuSyncer()
            results = syncer.sync_all()
            logger.info(f"飞书同步完成: {len(results.get('success', []))} 成功")
            return results
        except Exception as e:
            logger.error(f"飞书同步失败: {e}")
            return {'success': [], 'failed': [], 'skipped': 0}
    
    def _get_viewpoint_extractor(self):
        """获取观点提取器（延迟初始化）"""
        if self._viewpoint_extractor is None:
            try:
                from viewpoint_extractor import ViewPointExtractor
                self._viewpoint_extractor = ViewPointExtractor()
                logger.info("观点提取器初始化成功")
            except ImportError as e:
                logger.warning(f"观点提取器导入失败: {e}")
                self._viewpoint_extractor = None
        return self._viewpoint_extractor
    
    def extract_viewpoints_from_file(self, file_path: str, source: str) -> Optional[Dict]:
        """从转录文件提取观点
        
        Args:
            file_path: 转录文件路径
            source: 来源名称
            
        Returns:
            Optional[Dict]: 观点数据
        """
        if not self.enable_viewpoint:
            return None
        
        extractor = self._get_viewpoint_extractor()
        if extractor is None:
            logger.warning("观点提取器不可用")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if len(text) < 100:  # 内容太短，跳过
                return None
            
            viewpoint = extractor.extract(
                text=text,
                source=source,
                source_url='',
            )
            
            return {
                'source': viewpoint.source,
                'content': viewpoint.content,
                'category': viewpoint.category,
                'highlights': viewpoint.highlights,
                'timestamp': viewpoint.timestamp,
            }
            
        except Exception as e:
            logger.warning(f"观点提取失败 [{source}]: {e}")
            return None
    
    def run_viewpoint_extraction(self, new_files: Dict[str, List[str]]) -> List[Dict]:
        """对新增文件执行观点提取
        
        Args:
            new_files: 各平台新增文件路径
                {
                    'xiaoyuzhou': ['path1.txt', 'path2.txt'],
                    'youtube': ['path3.txt'],
                    ...
                }
                
        Returns:
            List[Dict]: 观点列表
        """
        if not self.enable_viewpoint:
            logger.info("观点提取功能已禁用")
            return []
        
        logger.info("=" * 50)
        logger.info("开始观点提取")
        
        viewpoints = []
        
        for platform, files in new_files.items():
            for file_path in files:
                try:
                    source = Path(file_path).stem
                    viewpoint = self.extract_viewpoints_from_file(file_path, source)
                    
                    if viewpoint:
                        viewpoint['platform'] = platform
                        viewpoint['file_path'] = file_path
                        viewpoints.append(viewpoint)
                        logger.info(f"观点提取成功: {source}")
                        
                except Exception as e:
                    logger.warning(f"观点提取失败 [{file_path}]: {e}")
        
        logger.info(f"观点提取完成: {len(viewpoints)} 个")
        self.results['viewpoints'] = viewpoints
        
        return viewpoints
    
    def save_viewpoints(self) -> str:
        """保存观点提取结果"""
        if not self.results['viewpoints']:
            return ""
        
        output_dir = self._viewpoint_cache_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"viewpoints_{datetime.now().strftime('%Y%m%d')}.json"
        
        data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'viewpoints': self.results['viewpoints'],
            'extracted_at': datetime.now().isoformat(),
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"观点已保存: {output_file}")
        return str(output_file)
    
    def generate_summary(self) -> str:
        """生成执行摘要"""
        total_files = (
            len(self.results['xiaoyuzhou']) +
            len(self.results['youtube']) +
            len(self.results['bilibili']) +
            len(self.results['twitter'])
        )
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        lines = []
        lines.append("=" * 60)
        lines.append("内容监控系统 - 执行报告")
        lines.append("=" * 60)
        lines.append(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"耗时: {elapsed:.1f} 秒")
        lines.append("")
        lines.append("## 各平台处理结果\n")
        lines.append(f"- 小宇宙: {len(self.results['xiaoyuzhou'])} 个")
        lines.append(f"- YouTube: {len(self.results['youtube'])} 个")
        lines.append(f"- B站: {len(self.results['bilibili'])} 个")
        lines.append(f"- Twitter: {len(self.results['twitter'])} 个")
        lines.append("")
        lines.append(f"**总计处理: {total_files} 个新内容**")
        
        # 观点提取结果（v1.1.0新增）
        viewpoints = self.results.get('viewpoints', [])
        if viewpoints:
            lines.append("")
            lines.append("## 观点提取结果\n")
            lines.append(f"- 提取观点: {len(viewpoints)} 个")
            
            # 分类统计
            categories = {}
            for vp in viewpoints:
                cat = vp.get('category', '未知')
                categories[cat] = categories.get(cat, 0) + 1
            
            for cat, count in categories.items():
                lines.append(f"  - {cat}: {count} 个")
        
        lines.append("")
        
        # 飞书同步结果
        feishu = self.results.get('feishu', {})
        if feishu:
            lines.append("## 飞书同步结果\n")
            lines.append(f"- 成功: {len(feishu.get('success', []))} 个")
            lines.append(f"- 失败: {len(feishu.get('failed', []))} 个")
        
        lines.append("")
        lines.append("=" * 60)
        
        return '\n'.join(lines)
    
    def save_report(self) -> str:
        """保存执行报告"""
        report_dir = LOG_DIR
        report_path = report_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report_data = {
            'start_time': self.start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'elapsed_seconds': (datetime.now() - self.start_time).total_seconds(),
            'results': {
                'xiaoyuzhou': self.results['xiaoyuzhou'],
                'youtube': self.results['youtube'],
                'bilibili': self.results['bilibili'],
                'twitter': self.results['twitter'],
            },
            'feishu_sync': {
                'success': len(self.results['feishu'].get('success', [])),
                'failed': len(self.results['feishu'].get('failed', [])),
            }
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"报告已保存: {report_path}")
        return str(report_path)
    
    def run_all(self, sync_to_feishu: bool = True, extract_viewpoints: bool = True) -> Dict:
        """执行所有监控任务
        
        Args:
            sync_to_feishu: 是否同步到飞书
            extract_viewpoints: 是否提取观点
        """
        logger.info("=" * 60)
        logger.info("内容监控系统启动")
        logger.info("=" * 60)
        
        # 检查依赖
        if not self.check_dependencies():
            logger.warning("依赖检查失败，继续执行...")
        
        # 执行各平台监控
        self.results['xiaoyuzhou'] = self.run_xiaoyuzhou()
        self.results['youtube'] = self.run_youtube()
        self.results['bilibili'] = self.run_bilibili()
        self.results['twitter'] = self.run_twitter()
        
        # 飞书同步
        if sync_to_feishu:
            all_files = (
                self.results['xiaoyuzhou'] +
                self.results['youtube'] +
                self.results['bilibili'] +
                self.results['twitter']
            )
            if all_files:
                self.results['feishu'] = self.run_feishu_sync(all_files)
        
        # 观点提取（新增功能）
        if extract_viewpoints and self.enable_viewpoint:
            new_files = {
                'xiaoyuzhou': self.results['xiaoyuzhou'],
                'youtube': self.results['youtube'],
                'bilibili': self.results['bilibili'],
                'twitter': self.results['twitter'],
            }
            self.run_viewpoint_extraction(new_files)
            self.save_viewpoints()
        
        # 生成报告
        summary = self.generate_summary()
        report_path = self.save_report()
        
        print("\n" + summary)
        
        return self.results


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='内容监控系统')
    parser.add_argument('--no-sync', action='store_true', help='跳过飞书同步')
    parser.add_argument('--platform', choices=['xiaoyuzhou', 'youtube', 'bilibili', 'twitter', 'all'],
                       default='all', help='指定运行平台')
    args = parser.parse_args()
    
    monitor = ContentMonitor()
    
    if args.platform == 'all':
        monitor.run_all(sync_to_feishu=not args.no_sync)
    else:
        # 运行指定平台
        if args.platform == 'xiaoyuzhou':
            monitor.results['xiaoyuzhou'] = monitor.run_xiaoyuzhou()
        elif args.platform == 'youtube':
            monitor.results['youtube'] = monitor.run_youtube()
        elif args.platform == 'bilibili':
            monitor.results['bilibili'] = monitor.run_bilibili()
        elif args.platform == 'twitter':
            monitor.results['twitter'] = monitor.run_twitter()
        
        summary = monitor.generate_summary()
        print(summary)


if __name__ == "__main__":
    main()


# 错误处理装饰器
def retry_on_failure(max_retries=3, delay=60, exceptions=(Exception,)):
    """
    失败重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 重试间隔（秒）
        exceptions: 需要捕获的异常类型
    """
    import time
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"第{attempt+1}次尝试失败: {e}，{delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"已达到最大重试次数({max_retries})，放弃执行")
            raise last_exception
        return wrapper
    return decorator


def safe_execute(func, *args, default=None, **kwargs):
    """
    安全执行函数，失败时返回默认值
    
    Args:
        func: 要执行的函数
        default: 失败时的默认返回值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"执行失败: {func.__name__}, 错误: {e}")
        return default


def validate_config(config_path):
    """
    验证配置文件格式
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        (is_valid, errors): 是否有效，错误列表
    """
    errors = []
    
    if not os.path.exists(config_path):
        errors.append(f"配置文件不存在: {config_path}")
        return False, errors
    
    # 检查必要的section
    required_sections = ['小宇宙', 'YouTube', 'B站', 'Twitter']
    
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for section in required_sections:
        if section not in content:
            errors.append(f"缺少配置section: {section}")
    
    return len(errors) == 0, errors


def notify_master(message, channel='coze'):
    """
    通知主人任务结果
    
    安全说明：不使用subprocess执行外部命令，避免供应链攻击风险
    
    Args:
        message: 通知内容
        channel: 通知渠道（coze/feishu）
    """
    # 安全：仅使用日志记录，不调用外部CLI工具
    # 如需飞书通知，请使用 lark-oapi Python SDK
    
    if channel == 'feishu':
        # 安全方式：使用飞书官方SDK（需要先安装 lark-oapi）
        try:
            # 导入飞书SDK（需要预先配置）
            # from lark_oapi.api.im.v1 import CreateMessageRequest
            # 这里仅记录日志，实际通知由调用方通过安全方式实现
            logger.info(f"[飞书通知] {message}")
            logger.warning("飞书通知需要使用lark-oapi SDK，请检查配置")
        except Exception as e:
            logger.error(f"飞书通知失败: {e}")
    else:
        # 默认在对话中通知（通过日志）
        logger.info(f"[通知] {message}")
