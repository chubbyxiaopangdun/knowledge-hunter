#!/bin/bash
# Content Monitor 安装脚本

set -e

echo "======================================"
echo "  Content Monitor 安装脚本"
echo "======================================"
echo ""

# 检查Python版本
echo "检查Python版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python版本: $python_version"

if [[ ! "$python_version" =~ ^3\.(10|11|12|13) ]]; then
    echo "⚠️  警告: 推荐使用Python 3.10+"
fi

# 安装基础依赖
echo ""
echo "安装基础依赖..."
pip3 install -q feedparser httpx beautifulsoup4 lxml

# 安装视频下载工具
echo ""
echo "安装视频下载工具..."
pip3 install -q yt-dlp

# 检查ffmpeg
echo ""
echo "检查ffmpeg..."
if command -v ffmpeg &> /dev/null; then
    echo "✓ ffmpeg已安装"
else
    echo "⚠️  ffmpeg未安装，正在安装..."
    apt-get update -qq && apt-get install -y -qq ffmpeg
fi

# 安装Whisper（可选，较大）
echo ""
echo "是否安装Whisper转录模型？(y/n)"
echo "（约需2GB空间，安装时间较长）"
read -r install_whisper

if [[ "$install_whisper" =~ ^[Yy]$ ]]; then
    echo ""
    echo "安装Whisper..."
    pip3 install -q openai-whisper
    
    # 预下载模型
    echo ""
    echo "预下载Whisper base模型..."
    python3 -c "import whisper; whisper.load_model('base')"
    echo "✓ Whisper安装完成"
else
    echo "跳过Whisper安装"
fi

# 检查lark-cli
echo ""
echo "检查飞书CLI..."
if command -v lark-cli &> /dev/null; then
    echo "✓ lark-cli已安装"
else
    echo "⚠️  lark-cli未安装"
    echo "请手动安装: pip install lark-cli"
fi

# 创建目录结构
echo ""
echo "创建目录结构..."
mkdir -p ./内容监控/输出/{小宇宙,YouTube,B站,Twitter}
mkdir -p ./内容监控/日志
mkdir -p ./内容监控/测试报告
echo "✓ 目录创建完成"

# 验证安装
echo ""
echo "======================================"
echo "  安装验证"
echo "======================================"

python3 << 'EOF'
import sys
dependencies = {
    'feedparser': 'RSS解析',
    'httpx': 'HTTP请求',
    'bs4': 'HTML解析',
    'yt_dlp': '视频下载',
}

all_ok = True
for module, desc in dependencies.items():
    try:
        __import__(module)
        print(f"✓ {desc} ({module})")
    except ImportError:
        print(f"✗ {desc} ({module}) - 未安装")
        all_ok = False

# 检查Whisper
try:
    import whisper
    print(f"✓ Whisper转录")
except ImportError:
    print(f"⚠ Whisper转录 - 未安装（可选）")

# 检查ffmpeg
import subprocess
try:
    subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    print(f"✓ FFmpeg")
except:
    print(f"✗ FFmpeg - 未安装")
    all_ok = False

if all_ok:
    print("\n✅ 所有核心依赖安装成功！")
else:
    print("\n⚠️ 部分依赖安装失败，请检查")
    sys.exit(1)
EOF

echo ""
echo "======================================"
echo "  安装完成！"
echo "======================================"
echo ""
echo "下一步："
echo "1. 编辑 ./内容监控/配置/博主列表.md 添加监控目标"
echo "2. 运行 python3 ./内容监控/scripts/monitor.py 开始监控"
echo "3. 或告诉诺诺 '执行内容监控系统'"
echo ""
