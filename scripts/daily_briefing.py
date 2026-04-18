#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日简报推送任务 - 定时生成并推送每日简报
整合观点提取、评分、冲突检测、简报生成功能
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

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
        logging.FileHandler(LOG_DIR / f"daily_briefing_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger(__name__)


class DailyBriefingTask:
    """每日简报任务主类
    
    工作流程：
    1. 收集近期监控内容（转录稿）
    2. 调用观点提取器提取观点
    3. 调用内容评分器打分
    4. 调用冲突检测器检测观点冲突
    5. 调用简报生成器生成简报
    6. 推送到飞书
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化任务
        
        Args:
            config: 配置字典
        """
        self.config = config or self._load_config()
        self.base_dir = SCRIPT_DIR.parent
        
        # 初始化各模块
        self._init_modules()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        config_path = self.base_dir / "配置" / "简报配置.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"配置加载失败: {e}")
        
        # 默认配置
        return {
            'push_time': '09:00',           # 推送时间
            'feishu_webhook': '',           # 飞书Webhook
            'feishu_chat_id': '',           # 飞书群ID
            'video_count': 3,               # 视频数量
            'podcast_count': 2,             # 播客数量
            'conflict_count': 1,            # 冲突数量
            'score_threshold': 6.0,         # 评分阈值
            'days_range': 1,                # 内容时间范围（天）
        }
    
    def _init_modules(self):
        """初始化各功能模块"""
        try:
            from viewpoint_extractor import ViewPointExtractor
            from content_scorer import ContentScorer
            from conflict_detector import ConflictDetector
            from briefing_generator import BriefingGenerator
            
            self.extractor = ViewPointExtractor()
            self.scorer = ContentScorer()
            self.detector = ConflictDetector()
            self.generator = BriefingGenerator()
            
            logger.info("所有模块初始化成功")
        except ImportError as e:
            logger.error(f"模块导入失败: {e}")
            raise
    
    def run(self, date: Optional[str] = None) -> Tuple[str, str]:
        """执行每日简报任务
        
        Args:
            date: 指定日期，默认为昨天
            
        Returns:
            Tuple[str, str]: (简报Markdown, 保存路径)
        """
        if date is None:
            # 默认处理昨天的内容
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        logger.info("=" * 60)
        logger.info(f"开始生成每日简报: {date}")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        
        try:
            # Step 1: 收集近期内容
            contents = self._collect_contents(date)
            logger.info(f"收集到 {len(contents)} 条内容")
            
            if not contents:
                logger.warning("没有新内容，跳过简报生成")
                return "", ""
            
            # Step 2: 提取观点
            viewpoints = self._extract_viewpoints(contents)
            logger.info(f"提取了 {len(viewpoints)} 个观点")
            
            # Step 3: 评分
            scores = self._score_contents(contents, viewpoints)
            logger.info(f"评分了 {len(scores)} 条内容")
            
            # Step 4: 检测冲突
            conflicts = self._detect_conflicts(viewpoints)
            logger.info(f"检测到 {len(conflicts)} 个冲突")
            
            # Step 5: 筛选优质内容
            videos, podcasts = self._filter_contents(contents, viewpoints, scores)
            logger.info(f"筛选视频 {len(videos)} 个，播客 {len(podcasts)} 个")
            
            # Step 6: 生成简报
            briefing, data = self.generator.generate_and_save(
                date=date,
                videos=videos,
                podcasts=podcasts,
                conflicts=conflicts,
                scores=scores
            )
            
            # Step 7: 推送到飞书
            if self.config.get('feishu_webhook'):
                self._push_to_feishu(briefing)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"简报生成完成，耗时: {elapsed:.1f}秒")
            
            return briefing, str(self.generator.output_dir / f"简报_{date}.md")
            
        except Exception as e:
            logger.error(f"简报生成失败: {e}")
            raise
    
    def _collect_contents(self, date: str) -> List[Dict]:
        """收集指定日期的内容
        
        Args:
            date: 日期字符串 (YYYY-MM-DD)
            
        Returns:
            List[Dict]: 内容列表
        """
        contents = []
        
        # 定义各平台的输出目录
        platform_dirs = {
            'xiaoyuzhou': self.base_dir / "输出" / "小宇宙",
            'youtube': self.base_dir / "输出" / "YouTube",
            'bilibili': self.base_dir / "输出" / "B站",
        }
        
        for platform, dir_path in platform_dirs.items():
            if not dir_path.exists():
                continue
            
            # 查找指定日期的文件
            for file_path in dir_path.glob(f"*{date}*.txt"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                    
                    contents.append({
                        'text': text,
                        'source': file_path.stem.replace(f"_{date}", ""),
                        'source_url': '',
                        'platform': platform,
                        'file_path': str(file_path),
                    })
                except Exception as e:
                    logger.warning(f"读取文件失败: {file_path}, {e}")
        
        return contents
    
    def _extract_viewpoints(self, contents: List[Dict]) -> List[Dict]:
        """提取观点
        
        Args:
            contents: 内容列表
            
        Returns:
            List[Dict]: 包含观点的内容列表
        """
        viewpoints = []
        
        for content in contents:
            try:
                # 提取观点
                viewpoint = self.extractor.extract(
                    text=content['text'],
                    source=content['source'],
                    source_url=content.get('source_url', ''),
                )
                
                # 转换为字典
                vp_dict = {
                    'source': viewpoint.source,
                    'source_url': viewpoint.source_url,
                    'content': viewpoint.content,
                    'category': viewpoint.category,
                    'key_points': viewpoint.highlights,
                    'platform': content.get('platform', 'unknown'),
                }
                
                viewpoints.append(vp_dict)
                
                # 添加到冲突检测器
                self.detector.add_viewpoint(
                    content=viewpoint.content,
                    source=viewpoint.source,
                    source_url=viewpoint.source_url,
                    category=viewpoint.category,
                    key_points=viewpoint.highlights,
                )
                
            except Exception as e:
                logger.warning(f"观点提取失败 [{content.get('source', '未知')}]: {e}")
        
        return viewpoints
    
    def _score_contents(self, 
                        contents: List[Dict], 
                        viewpoints: List[Dict]) -> List[Dict]:
        """对内容评分
        
        Args:
            contents: 原始内容
            viewpoints: 观点数据
            
        Returns:
            List[Dict]: 评分结果
        """
        # 建立映射
        vp_map = {vp['source']: vp for vp in viewpoints}
        
        scores = []
        
        for content in contents:
            source = content['source']
            viewpoint = vp_map.get(source)
            
            try:
                score = self.scorer.score(
                    text=content['text'],
                    viewpoint=viewpoint,
                    source=source,
                    source_url=content.get('source_url', ''),
                )
                
                scores.append({
                    'source': score.source,
                    'source_url': score.source_url,
                    'total_score': score.total_score,
                    'viewpoint_quality': score.viewpoint_quality,
                    'info_density': score.info_density,
                    'originality': score.originality,
                    'is_worth_consuming': score.is_worth_consuming,
                    'recommendation': score.recommendation,
                    'category': score.category,
                })
                
            except Exception as e:
                logger.warning(f"评分失败 [{source}]: {e}")
        
        return scores
    
    def _detect_conflicts(self, viewpoints: List[Dict]) -> List[Dict]:
        """检测观点冲突
        
        Args:
            viewpoints: 观点列表
            
        Returns:
            List[Dict]: 冲突列表
        """
        try:
            conflicts = self.detector.detect_conflicts(viewpoints)
            
            return [
                {
                    'topic': c.topic,
                    'viewpoint_a': c.viewpoint_a,
                    'source_a': c.source_a,
                    'url_a': c.source_url_a,
                    'viewpoint_b': c.viewpoint_b,
                    'source_b': c.source_b,
                    'url_b': c.source_url_b,
                    'conflict_level': c.conflict_level,
                }
                for c in conflicts[:self.config.get('conflict_count', 1)]
            ]
        except Exception as e:
            logger.warning(f"冲突检测失败: {e}")
            return []
    
    def _filter_contents(self,
                         contents: List[Dict],
                         viewpoints: List[Dict],
                         scores: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """筛选优质内容
        
        Args:
            contents: 原始内容
            viewpoints: 观点数据
            scores: 评分结果
            
        Returns:
            Tuple[List[Dict], List[Dict]]: (视频列表, 播客列表)
        """
        threshold = self.config.get('score_threshold', 6.0)
        
        # 建立映射
        score_map = {s['source']: s for s in scores}
        vp_map = {vp['source']: vp for vp in viewpoints}
        
        videos = []
        podcasts = []
        
        for content in contents:
            source = content['source']
            score = score_map.get(source)
            viewpoint = vp_map.get(source)
            
            if not score or not score.get('is_worth_consuming', False):
                continue
            
            if score.get('total_score', 0) < threshold:
                continue
            
            item = {
                'title': source,
                'source': source,
                'url': content.get('source_url', ''),
                'score': score.get('total_score', 0),
                'recommendation': score.get('recommendation', ''),
                'category': viewpoint.get('category', '观点') if viewpoint else '观点',
                'viewpoint': viewpoint.get('key_points', []) if viewpoint else [],
            }
            
            platform = content.get('platform', '')
            if platform in ['youtube', 'bilibili']:
                videos.append(item)
            elif platform in ['xiaoyuzhou', 'podcast']:
                podcasts.append(item)
        
        # 按分数排序
        videos = sorted(videos, key=lambda x: x['score'], reverse=True)
        podcasts = sorted(podcasts, key=lambda x: x['score'], reverse=True)
        
        # 限制数量
        video_count = self.config.get('video_count', 3)
        podcast_count = self.config.get('podcast_count', 2)
        
        return videos[:video_count], podcasts[:podcast_count]
    
    def _push_to_feishu(self, briefing: str):
        """推送到飞书
        
        Args:
            briefing: 简报内容
        """
        try:
            webhook = self.config.get('feishu_webhook')
            if not webhook:
                logger.warning("未配置飞书Webhook")
                return
            
            import httpx
            
            # 构建飞书消息格式
            message = {
                "msg_type": "text",
                "content": {
                    "text": briefing
                }
            }
            
            # 发送请求
            response = httpx.post(webhook, json=message, timeout=30)
            
            if response.status_code == 200:
                logger.info("飞书推送成功")
            else:
                logger.error(f"飞书推送失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"飞书推送失败: {e}")


# 快捷函数：直接执行
def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='每日简报生成任务')
    parser.add_argument('--date', '-d', help='指定日期 (YYYY-MM-DD)')
    parser.add_argument('--config', '-c', help='配置文件路径')
    
    args = parser.parse_args()
    
    # 加载配置
    config = {}
    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建任务
    task = DailyBriefingTask(config)
    
    # 执行
    briefing, path = task.run(args.date)
    
    if briefing:
        print(f"\n✅ 简报生成成功！")
        print(f"📄 保存路径: {path}")
        print(f"📝 简报预览:\n{briefing[:500]}...")
    else:
        print("\n⚠️ 没有新内容或生成失败")


if __name__ == '__main__':
    main()
