#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper语音转文字模块
使用OpenAI开源Whisper模型进行语音转录
"""

import os
import whisper
import ffmpeg
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 模型缓存目录
MODEL_DIR = Path.home() / ".cache" / "whisper"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# 默认使用base模型（速度与质量平衡）
DEFAULT_MODEL = "base"


class WhisperTranscriber:
    """Whisper转录器封装"""
    
    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = "cpu"):
        """
        初始化转录器
        
        Args:
            model_name: 模型名称 (tiny/base/small/medium/large)
            device: 设备类型 (cpu/cuda)
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        logger.info(f"初始化Whisper {model_name} 模型 (设备: {device})")
    
    def load_model(self) -> None:
        """加载Whisper模型"""
        if self.model is None:
            logger.info(f"正在加载模型: {self.model_name}...")
            self.model = whisper.load_model(self.model_name, device=self.device)
            logger.info("模型加载完成")
    
    def transcribe_audio(
        self, 
        audio_path: str, 
        language: Optional[str] = "zh",
        output_format: str = "markdown",
        save_srt: bool = False
    ) -> Dict[str, Any]:
        """
        转录音频文件
        
        Args:
            audio_path: 音频文件路径
            language: 音频语言 (默认中文)
            output_format: 输出格式 (markdown/text/srt)
            save_srt: 是否保存SRT时间轴字幕
        
        Returns:
            包含转录结果的字典
        """
        self.load_model()
        
        logger.info(f"开始转录: {audio_path}")
        
        # 转录参数
        options = {
            "language": language,
            "task": "transcribe",
            "verbose": False,
        }
        
        # 执行转录
        result = self.model.transcribe(audio_path, **options)
        
        # 生成输出
        output = {
            "text": result["text"],
            "segments": result.get("segments", []),
            "language": result.get("language", language),
            "duration": result.get("duration", 0),
        }
        
        # 生成Markdown格式（带时间轴）
        if output_format == "markdown":
            output["markdown"] = self._generate_markdown(result["segments"], result.get("text", ""))
        
        # 保存SRT文件
        if save_srt and result.get("segments"):
            srt_path = audio_path.replace(os.path.splitext(audio_path)[1], ".srt")
            self._save_srt(result["segments"], srt_path)
            output["srt_path"] = srt_path
        
        logger.info(f"转录完成，时长: {output['duration']:.1f}秒")
        return output
    
    def _generate_markdown(self, segments: list, full_text: str) -> str:
        """生成带时间轴的Markdown格式"""
        lines = []
        lines.append("# 语音转录稿\n")
        lines.append("> 由 Whisper AI 自动转录\n")
        lines.append("")
        
        if not segments:
            lines.append(full_text)
            return "\n".join(lines)
        
        for seg in segments:
            start = self._format_time(seg["start"])
            end = self._format_time(seg["end"])
            text = seg["text"].strip()
            lines.append(f"[{start} → {end}] {text}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 完整文本")
        lines.append("")
        lines.append(full_text)
        
        return "\n".join(lines)
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间戳为 HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _save_srt(self, segments: list, output_path: str) -> None:
        """保存SRT字幕文件"""
        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                start = self._format_srt_time(seg["start"])
                end = self._format_srt_time(seg["end"])
                text = seg["text"].strip()
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{text}\n\n")
    
    def _format_srt_time(self, seconds: float) -> str:
        """格式化时间为SRT格式 HH:MM:SS,mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def download_and_transcribe(
    url: str, 
    platform: str,
    output_dir: str,
    model_name: str = DEFAULT_MODEL
) -> Optional[str]:
    """
    下载音频并转录的便捷函数
    
    Args:
        url: 视频/音频URL
        platform: 平台名称 (youtube/bilibili/xiaoyuzhou)
        output_dir: 输出目录
        model_name: Whisper模型名称
    
    Returns:
        转录结果Markdown文件路径，失败返回None
    """
    import yt_dlp
    
    transcriber = WhisperTranscriber(model_name=model_name)
    
    # 创建输出目录
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 下载音频
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            audio_path = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
        
        # 转录
        result = transcriber.transcribe_audio(audio_path)
        
        # 保存Markdown
        md_path = audio_path.replace('.mp3', '.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(result['markdown'])
        
        return md_path
        
    except Exception as e:
        logger.error(f"下载转录失败: {e}")
        return None


if __name__ == "__main__":
    # 测试代码
    transcriber = WhisperTranscriber()
    print(f"Whisper版本: {whisper.__version__}")
    print(f"模型目录: {MODEL_DIR}")
