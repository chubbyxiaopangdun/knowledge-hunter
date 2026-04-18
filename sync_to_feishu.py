#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书同步模块
将转录内容同步到飞书知识库
使用飞书CLI工具实现，避免SDK依赖
"""

import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeishuSyncer:
    """飞书同步器 - 使用飞书CLI实现"""
    
    def __init__(self, output_dir: str = "./内容监控/输出"):
        self.output_dir = Path(output_dir)
        
        # 飞书相关配置
        self.wiki_space = os.environ.get('FEISHU_WIKI_SPACE', 'my_library')
        self.root_folder = os.environ.get('FEISHU_ROOT_FOLDER', '内容监控')
        
        # 平台文件夹映射
        self.platform_folders = {
            "小宇宙": "小宇宙",
            "YouTube": "YouTube",
            "B站": "B站",
            "Twitter": "Twitter",
        }
    
    def check_lark_cli(self) -> bool:
        """检查lark-cli是否可用"""
        try:
            result = subprocess.run(
                ['lark', '--version'], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
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
            
            # 使用飞书CLI上传文档
            return self._upload_to_feishu(title, str(file_path), platform)
            
        except Exception as e:
            logger.error(f"处理文件失败 {file_path}: {e}")
            return None
    
    def _upload_to_feishu(
        self, 
        title: str, 
        file_path: str, 
        platform: str
    ) -> Optional[Dict]:
        """使用飞书CLI上传文档到知识库
        
        安全说明：使用lark-cli命令行工具，用户需自行安装和配置
        文档：https://github.com/nicepkg/lark-cli
        """
        try:
            # 构建文件夹路径
            folder_path = f"{self.root_folder}/{platform}"
            
            # 使用lark-cli上传文档
            cmd = [
                'lark', 'docx', 'upload',
                '--file', file_path,
                '--title', title,
                '--folder', folder_path,
                '--wiki', self.wiki_space
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info(f"文档上传成功: {title}")
                # 解析返回的文档URL
                doc_url = result.stdout.strip().split('\n')[-1] if result.stdout else ""
                return {
                    'success': True,
                    'title': title,
                    'url': doc_url
                }
            else:
                logger.error(f"文档上传失败: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("上传超时")
            return None
        except Exception as e:
            logger.error(f"上传异常: {e}")
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
