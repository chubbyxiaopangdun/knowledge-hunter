#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识猎手 - 一键安装配置脚本
帮助新手快速完成所有配置
安全修复：移除subprocess调用，使用shutil和pip内部API
"""

import os
import sys
import shutil
from pathlib import Path


def print_step(step, total, message):
    """打印步骤信息"""
    print(f"\n{'='*50}")
    print(f"[{step}/{total}] {message}")
    print('='*50)


def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python版本过低，需要 3.8+")
        print(f"   当前版本: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
    return True


def check_ffmpeg():
    """检查FFmpeg是否安装（安全方式）"""
    path = shutil.which('ffmpeg')
    if path:
        print(f"✅ FFmpeg 已安装: {path}")
        return True
    
    print("⚠️ FFmpeg 未安装")
    print("\n安装方法：")
    print("  Ubuntu/Debian: sudo apt install ffmpeg")
    print("  macOS: brew install ffmpeg")
    print("  Windows: 从 https://ffmpeg.org/download.html 下载")
    return False


def install_dependencies():
    """安装Python依赖（安全方式：使用pip内部API）"""
    print("\n正在安装Python依赖...")
    
    requirements = [
        "openai-whisper",
        "yt-dlp",
        "feedparser",
        "httpx",
        "requests",
        "python-dateutil",
        "tqdm",
    ]
    
    try:
        # 使用pip内部API而不是subprocess
        from pip._internal.cli.main import main as pip_main
        
        for package in requirements:
            print(f"  安装 {package}...")
            try:
                result = pip_main(['install', package, '-q'])
                if result == 0:
                    print(f"  ✅ {package}")
                else:
                    print(f"  ❌ {package} 安装失败")
                    return False
            except Exception as e:
                print(f"  ❌ {package} 安装失败: {e}")
                return False
        
        print("\n✅ 所有依赖安装完成")
        return True
        
    except ImportError:
        print("⚠️ 无法使用pip内部API，请手动安装：")
        print("pip install " + " ".join(requirements))
        return False


def create_directories():
    """创建必要的目录结构"""
    print("\n创建目录结构...")
    
    dirs = [
        "./内容监控",
        "./内容监控/配置",
        "./内容监控/输出",
        "./内容监控/输出/小宇宙",
        "./内容监控/输出/YouTube",
        "./内容监控/输出/B站",
        "./内容监控/输出/Twitter",
        "./内容监控/日志",
    ]
    
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {d}")
    
    print("\n✅ 目录创建完成")
    return True


def create_default_config():
    """创建默认配置文件"""
    print("\n创建默认配置文件...")
    
    config_path = Path("./内容监控/配置/博主列表.md")
    
    if config_path.exists():
        print(f"  ⚠️ 配置文件已存在: {config_path}")
        return True
    
    default_config = '''# 知识猎手 - 博主监控列表

> 在下方添加你要监控的博主/频道，支持多个平台

---

## 小宇宙播客

| 名称 | RSS地址/链接 | 备注 |
|------|-------------|------|
| 示例播客 | https://feed.xyzfm.space/example | 请替换为实际RSS |

<!-- 添加更多播客：复制上面的行，填入真实信息 -->

---

## YouTube频道

| 名称 | 频道ID | 备注 |
|------|--------|------|
| 示例频道 | UCxxxxxxx | 请替换为实际频道ID |

<!-- 频道ID获取方法：打开频道页面，URL中 channel/ 后面的字符串 -->

---

## B站UP主

| 名称 | UID | 备注 |
|------|-----|------|
| 示例UP主 | 12345678 | 请替换为实际UID |

<!-- UID获取方法：打开UP主主页，URL中的数字 -->

**注意**：B站需要登录态才能下载部分视频，请配置环境变量：
```bash
export BILIBILI_SESSDATA="你的SESSDATA值"
```

---

## Twitter账号

| 名称 | 用户名 | 备注 |
|------|--------|------|
| 示例账号 | @username | 请替换为实际用户名 |

<!-- 用户名：@符号后面的部分 -->

---

*创建时间：自动生成*
*最后更新：请在添加博主后手动更新*
'''
    
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(default_config)
    
    print(f"  ✅ 已创建: {config_path}")
    print("  📝 请编辑此文件，添加你要监控的博主")
    return True


def download_whisper_model():
    """预下载Whisper模型"""
    print("\n预下载Whisper模型...")
    print("模型选项: tiny(最快), base(推荐), small(更准), medium(最准但最慢)")
    
    choice = input("\n选择模型 [tiny/base/small/medium] (默认base): ").strip().lower()
    if not choice:
        choice = 'base'
    
    if choice not in ['tiny', 'base', 'small', 'medium']:
        print("⚠️ 无效选择，使用默认 base 模型")
        choice = 'base'
    
    print(f"\n正在下载 {choice} 模型（首次下载较慢，请耐心等待）...")
    
    try:
        import whisper
        model = whisper.load_model(choice)
        print(f"✅ {choice} 模型下载完成")
        return True
    except Exception as e:
        print(f"⚠️ 模型下载失败: {e}")
        print("  首次使用时会自动下载")
        return True


def create_env_template():
    """创建环境变量模板"""
    print("\n创建环境变量模板...")
    
    env_path = Path("./内容监控/配置/.env.example")
    
    env_content = '''# 知识猎手 - 环境变量配置
# 复制此文件为 .env 并填入实际值

# B站登录态（可选，用于下载需要登录的视频）
# 获取方法：登录B站 → F12打开开发者工具 → Application → Cookies → 找到SESSDATA
BILIBILI_SESSDATA=

# 飞书配置（可选，用于同步到飞书知识库）
FEISHU_APP_ID=
FEISHU_APP_SECRET=

# Twitter API（可选，提高推文获取稳定性）
TWITTER_API_KEY=
TWITTER_API_SECRET=
'''
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"  ✅ 已创建: {env_path}")
    return True


def main():
    """主安装流程"""
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║       🎯 知识猎手 - 一键安装配置向导                         ║
║                                                            ║
║       主动出击，精准捕获有价值的内容                         ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")
    
    total_steps = 7
    current_step = 0
    
    # 步骤1：检查Python版本
    current_step += 1
    print_step(current_step, total_steps, "检查Python版本")
    if not check_python_version():
        sys.exit(1)
    
    # 步骤2：检查FFmpeg
    current_step += 1
    print_step(current_step, total_steps, "检查FFmpeg")
    check_ffmpeg()
    
    # 步骤3：安装依赖
    current_step += 1
    print_step(current_step, total_steps, "安装Python依赖")
    if not install_dependencies():
        print("\n❌ 依赖安装失败，请检查网络连接")
        sys.exit(1)
    
    # 步骤4：创建目录
    current_step += 1
    print_step(current_step, total_steps, "创建目录结构")
    create_directories()
    
    # 步骤5：创建配置文件
    current_step += 1
    print_step(current_step, total_steps, "创建默认配置")
    create_default_config()
    create_env_template()
    
    # 步骤6：下载Whisper模型
    current_step += 1
    print_step(current_step, total_steps, "下载Whisper模型")
    download_whisper_model()
    
    # 步骤7：完成
    current_step += 1
    print_step(current_step, total_steps, "安装完成！")
    
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║                    ✅ 安装成功！                            ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝

📋 下一步操作：

1. 编辑配置文件，添加你要监控的博主：
   ./内容监控/配置/博主列表.md

2. （可选）配置环境变量：
   cp ./内容监控/配置/.env.example ./内容监控/配置/.env
   # 然后编辑 .env 填入实际值

3. 运行监控：
   python scripts/monitor.py

4. 测试单个平台：
   python scripts/xiaoyuzhou.py
   python scripts/youtube.py

📚 更多帮助：
   查看 SKILL.md 了解详细用法
   查看 references/常见问题.md 解决常见问题

祝使用愉快！🐱
""")


if __name__ == "__main__":
    main()
