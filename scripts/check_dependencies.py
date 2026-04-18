#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
依赖验证脚本
检查所有依赖是否正确安装
安全修复：使用shutil.which替代subprocess检测命令
"""

import sys
import shutil

def check_module(name, import_name=None):
    """检查模块是否可导入"""
    if import_name is None:
        import_name = name
    
    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✅ {name}: {version}")
        return True
    except ImportError:
        print(f"❌ {name}: 未安装")
        return False

def check_command(name):
    """检查命令行工具是否可用（安全方式）"""
    path = shutil.which(name)
    if path:
        print(f"✅ {name}: {path}")
        return True
    else:
        print(f"❌ {name}: 未安装或不可用")
        return False

def main():
    print("=" * 50)
    print("内容监控系统 - 依赖检查")
    print("=" * 50)
    print()
    
    all_ok = True
    
    print("【Python模块】")
    all_ok &= check_module("feedparser")
    all_ok &= check_module("httpx")
    all_ok &= check_module("pytz")
    all_ok &= check_module("yt-dlp", "yt_dlp")
    all_ok &= check_module("Whisper", "whisper")  # 可能未安装
    all_ok &= check_module("torch", "torch")  # 可能未安装
    all_ok &= check_module("pandas", "pandas")  # 可选
    
    print()
    print("【命令行工具】")
    all_ok &= check_command("ffmpeg")
    all_ok &= check_command("python3")
    
    print()
    print("=" * 50)
    
    if all_ok:
        print("✅ 所有依赖检查通过！")
        print()
        print("下一步：")
        print("1. 编辑 ./内容监控/配置/博主列表.md 添加博主")
        print("2. 运行: python3 ./内容监控/scripts/monitor.py --no-sync")
    else:
        print("⚠️ 部分依赖缺失")
        print()
        print("安装命令：")
        print("pip3 install feedparser httpx pytz yt-dlp openai-whisper \\")
        print("         -i https://pypi.tuna.tsinghua.edu.cn/simple")
        print()
        print("详细说明见: ./内容监控/scripts/WHISPER安装说明.md")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
