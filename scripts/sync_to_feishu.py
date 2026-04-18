#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书同步模块
将转录内容同步到飞书知识库
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeishuSyncer:
    """飞书同步器"""
    
    def __init__(self, output_dir: str = "./内容监控/输出"):
        self.output_dir = Path(output_dir)
        
        # 飞书相关配置
        self.wiki_space = "my_library"
        self.root_folder = "内容监控"
        
        # 平台文件夹映射
        self.platform_folders = {
            "小宇宙": "小宇宙",
            "YouTube": "YouTube",
            "B站": "B站",
            "Twitter": "Twitter",
        }
    
    def get_pending_files(self) -> Dict[str, List[Path]]:
        """获取待同步的文件"""
        pending = {}
        
        for platform, folder in self.platform_folders.items():
            platform_dir = self.output_dir / folder
            
            if not platform_dir.exists():
                continue
            
            # 获取该平台下的md文件
            files = list(platform_dir.glob("*.md"))
            
            if files:
                pending[platform] = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
        
        return pending
    
    def create_doc_from_file(self, file_path: Path, platform: str) -> Optional[Dict]:
        """从文件创建飞书文档"""
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取标题（第一个#开头的行）
            title_match = content.split('\n')[0] if content else None
            title = title_match.lstrip('#').strip() if title_match else file_path.stem
            
            # 构建Markdown（移除第一个标题，避免重复）
            md_content = '\n'.join(content.split('\n')[2:]) if len(content.split('\n')) > 2 else content
            
            # 调用lark-cli创建文档
            return self._create_lark_doc(title, md_content, platform)
            
        except Exception as e:
            logger.error(f"处理文件失败 {file_path}: {e}")
            return None
    
    def _create_lark_doc(
        self, 
        title: str, 
        content: str, 
        platform: str
    ) -> Optional[Dict]:
        """使用lark-cli创建文档"""
        import subprocess
        
        # 构建命令
        wiki_node = self._get_wiki_node(platform)
        
        cmd = [
            "python3",
            ".skills/skill_feishu_doc/scripts/create_doc.py",
            "--title", title,
            "--markdown", content,
            "--wiki-space", self.wiki_space,
        ]
        
        if wiki_node:
            cmd.extend(["--wiki-node", wiki_node])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd="/app/data/所有对话/主对话"
            )
            
            if result.returncode == 0:
                output = json.loads(result.stdout)
                logger.info(f"文档创建成功: {output.get('doc_url', 'N/A')}")
                return output
            else:
                logger.error(f"文档创建失败: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("文档创建超时")
            return None
        except Exception as e:
            logger.error(f"调用lark-cli失败: {e}")
            return None
    
    def _get_wiki_node(self, platform: str) -> Optional[str]:
        """获取平台对应的wiki节点ID"""
        # 可以配置固定的wiki节点ID
        # 目前使用my_library直接创建
        return None
    
    def sync_all(self, dry_run: bool = False) -> Dict[str, List]:
        """同步所有待处理文件"""
        pending = self.get_pending_files()
        
        results = {
            'success': [],
            'failed': [],
            'skipped': 0,
        }
        
        total_files = sum(len(files) for files in pending.values())
        logger.info(f"待同步文件数: {total_files}")
        
        if total_files == 0:
            logger.info("没有待同步的文件")
            return results
        
        for platform, files in pending.items():
            logger.info(f"处理平台: {platform} ({len(files)} 个文件)")
            
            for file_path in files:
                logger.info(f"  处理文件: {file_path.name}")
                
                if dry_run:
                    results['skipped'] += 1
                    continue
                
                doc_result = self.create_doc_from_file(file_path, platform)
                
                if doc_result:
                    results['success'].append({
                        'platform': platform,
                        'file': str(file_path),
                        'doc_url': doc_result.get('doc_url'),
                        'doc_id': doc_result.get('doc_id'),
                    })
                else:
                    results['failed'].append({
                        'platform': platform,
                        'file': str(file_path),
                    })
        
        return results
    
    def generate_report(self, results: Dict) -> str:
        """生成同步报告"""
        lines = []
        lines.append(f"# 飞书同步报告\n")
        lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("\n---\n\n")
        
        lines.append(f"## 同步结果汇总\n\n")
        lines.append(f"- ✅ 成功: {len(results['success'])} 个\n")
        lines.append(f"- ❌ 失败: {len(results['failed'])} 个\n")
        lines.append(f"- ⏭️ 跳过: {results['skipped']} 个\n")
        lines.append("\n")
        
        if results['success']:
            lines.append("## 成功同步\n\n")
            for item in results['success']:
                lines.append(f"- **{item['platform']}**: {item['doc_url']}\n")
            lines.append("\n")
        
        if results['failed']:
            lines.append("## 失败列表\n\n")
            for item in results['failed']:
                lines.append(f"- {item['platform']}: {item['file']}\n")
            lines.append("\n")
        
        return ''.join(lines)
    
    def save_report(self, results: Dict, output_path: str = None) -> str:
        """保存同步报告"""
        if output_path is None:
            output_path = f"./内容监控/log/飞书同步报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        content = self.generate_report(results)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"报告已保存: {output_path}")
        return output_path


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='飞书同步工具')
    parser.add_argument('--dry-run', action='store_true', help='仅预览不同步')
    parser.add_argument('--output-dir', default='./内容监控/输出', help='输出目录')
    args = parser.parse_args()
    
    syncer = FeishuSyncer(output_dir=args.output_dir)
    
    if args.dry_run:
        logger.info("=== 预览模式 ===")
        pending = syncer.get_pending_files()
        total = sum(len(files) for files in pending.values())
        print(f"\n待同步文件数: {total}\n")
        for platform, files in pending.items():
            print(f"{platform}:")
            for f in files:
                print(f"  - {f.name}")
        return
    
    results = syncer.sync_all()
    report_path = syncer.save_report(results)
    
    print(f"\n=== 同步完成 ===")
    print(f"成功: {len(results['success'])}")
    print(f"失败: {len(results['failed'])}")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
