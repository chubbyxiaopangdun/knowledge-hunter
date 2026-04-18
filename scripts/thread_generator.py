# -*- coding: utf-8 -*-
"""
Thread 生成器 v2.0
基于热点话题和金句，生成可直接发布的Twitter Thread / 小红书文案

支持格式：
1. Twitter Thread（5-10条推文）
2. 小红书图文（标题 + 正文 + 标签）
3. 公众号文章大纲
"""

import re
from typing import List, Dict, Optional


# ============================================================
# Prompt 模板
# ============================================================

THREAD_PROMPT = """你是一个Twitter内容创作者。请基于以下素材生成1个Twitter Thread。

## 基本要求
- 共{line_count}条推文
- 每条不超过200字（Twitter限制280字符，这里留出转发空间）
- 语言风格：直接、有力、带一点情绪感，不要太学术

## 结构要求
1. 第1条是「钩子」- 用惊人事实/观点/问题吸引人注意
2. 中间2-3条是「核心观点」- 展开你的论点，每条聚焦一个点
3. 最后1条是「行动号召」- 让粉丝互动/转发/评论

## 素材要求
- 所有内容必须来自「可用素材」
- 不要自己编造数据或观点
- 如果素材不够，基于给定素材合理延伸

---
## 可用素材

**热点话题**：{topic}
**话题简述**：{topic_desc}

**可用金句**（选择2-3个最相关的）：
{gold_sentences}

**内容格式**：Twitter Thread
---

## 输出格式（严格按此格式）

```
【Tweet 1/{total}】
{内容}

【Tweet 2/{total}】
{内容}

……（共{line_count}条）
```"""


XIAOHONGSHU_PROMPT = """你是一个小红书内容创作者。请基于以下素材生成1篇小红书图文。

## 基本要求
- 标题：吸引眼球，引发好奇（可加emoji）
- 正文：300-500字，自然口语化，像和朋友聊天
- 标签：5-8个相关标签

## 结构要求
1. 开头：「姐妹们/兄弟们/听说了吗」- 引发注意
2. 中间：2-3个核心观点，每个用具体例子支撑
3. 结尾：「评论区告诉我」/「收藏慢慢看」- 引导互动

## 素材要求
- 所有内容必须来自「可用素材」
- 不要自己编造

---
## 可用素材

**热点话题**：{topic}
**话题简述**：{topic_desc}

**可用金句**（选择1-2个最相关的）：
{gold_sentences}

---

## 输出格式

```
【标题】
{标题}

【正文】
{正文内容}

【标签】
#标签1 #标签2 #标签3 ...
```"""


ARTICLE_OUTLINE_PROMPT = """你是一个公众号内容创作者。请基于以下素材生成一篇文章大纲。

## 基本要求
- 大纲格式，包含各章节的「核心论点」和「支撑素材」
- 语言风格：公众号风格，有观点有态度
- 适合人群：有独立思考能力的职场人/创业者

## 结构要求
1. 开头：用一个故事/场景/数据引发共鸣
2. 中间：3-4个核心论点，每个有具体案例或数据
3. 结尾：升华到一个更普遍的观点，附行动建议

## 素材要求
- 所有论点必须有素材支撑
- 不要自己编造

---
## 可用素材

**热点话题**：{topic}
**话题简述**：{topic_desc}

**可用金句**：
{gold_sentences}

---

## 输出格式

```
【文章标题】

一、开头（引发共鸣）
- 核心场景/故事：XXX
- 引发的问题：XXX

二、论点1（核心观点）
- 核心观点：XXX
- 支撑案例/数据：XXX
- 金句引用：XXX

三、论点2（深化）
...（共3-4个论点）

四、结尾（升华 + 行动建议）
- 升华观点：XXX
- 行动建议：XXX
```"""


# ============================================================
# 解析函数
# ============================================================

def parse_thread_response(text: str, line_count: int = 5) -> List[str]:
    """
    解析LLM输出的Thread
    
    Args:
        text: LLM返回的文本
        line_count: 预期的推文数量
    
    Returns:
        ["推文1内容", "推文2内容", ...]
    """
    tweets = []
    
    # 匹配格式：【Tweet 1/5】...【Tweet 2/5】...
    pattern = r'【Tweet \d+/\d+】\s*\n?(.*?)(?=【Tweet|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    if matches:
        tweets = [m.strip() for m in matches]
    else:
        # 备选：按行分割
        lines = text.split("\n")
        current_tweet = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if "【Tweet" in line:
                if current_tweet:
                    tweets.append("\n".join(current_tweet))
                    current_tweet = []
            else:
                current_tweet.append(line)
        
        if current_tweet:
            tweets.append("\n".join(current_tweet))
    
    return tweets[:line_count]


def parse_xiaohongshu_response(text: str) -> Dict[str, str]:
    """
    解析小红书文案
    
    Returns:
        {title, content, tags}
    """
    result = {
        "title": "",
        "content": "",
        "tags": ""
    }
    
    # 提取标题
    title_match = re.search(r'【标题】\s*\n?(.*?)(?=\[【正文】|【正文】|$)', text, re.DOTALL)
    if title_match:
        result["title"] = title_match.group(1).strip()
    
    # 提取正文
    content_match = re.search(r'【正文】\s*\n?(.*?)(?=\[【标签】|【标签】|$)', text, re.DOTALL)
    if content_match:
        result["content"] = content_match.group(1).strip()
    
    # 提取标签
    tags_match = re.search(r'【标签】\s*\n?(.*?)$', text, re.DOTALL)
    if tags_match:
        result["tags"] = tags_match.group(1).strip()
    
    return result


def parse_article_outline(text: str) -> str:
    """解析文章大纲"""
    return text.strip()


# ============================================================
# 格式化函数
# ============================================================

def format_thread(tweets: List[str]) -> str:
    """
    格式化Thread用于显示/复制
    
    Args:
        tweets: 推文列表
    
    Returns:
        Markdown格式
    """
    total = len(tweets)
    lines = [f"# ✏️ 今日可做：Twitter Thread（共{total}条）\n"]
    
    for i, tweet in enumerate(tweets, 1):
        lines.append(f"## Tweet {i}/{total}")
        lines.append(tweet)
        lines.append("")
    
    lines.append("---\n*可直接复制发布，每条Tweet单独发送*")
    
    return "\n\n".join(lines)


def format_xiaohongshu(data: Dict[str, str]) -> str:
    """格式化小红书文案"""
    lines = [
        "# ✏️ 今日可做：小红书图文\n",
        f"## 标题\n{data.get('title', '（未生成）')}\n",
        f"## 正文\n{data.get('content', '（未生成）')}\n",
        f"## 标签\n{data.get('tags', '（未生成）')}\n",
        "---\n*可直接复制发布*"
    ]
    
    return "\n".join(lines)


def format_article_outline(outline: str) -> str:
    """格式化文章大纲"""
    return f"# ✏️ 今日可做：公众号文章大纲\n\n{outline}\n\n---\n*可根据大纲扩写成完整文章*" 


# ============================================================
# 主函数
# ============================================================

def generate_thread(
    topic: str,
    gold_sentences: List[Dict],
    line_count: int = 5,
    content_type: str = "thread",
    use_llm: bool = True
) -> str:
    """
    生成短内容的主函数
    
    Args:
        topic: 热点话题
        gold_sentences: 金句列表 [{text, source, ...}, ...]
        line_count: Thread的推文数量
        content_type: 内容格式 ("thread" / "xiaohongshu" / "article")
        use_llm: 是否使用LLM
    
    Returns:
        格式化后的内容
    """
    if not topic:
        return "⚠️ 未提供话题，无法生成内容"
    
    if not gold_sentences:
        gold_sentences = [{
            "text": "（无可用金句，请基于话题自行发挥）",
            "source": "系统生成",
            "speaker": "未识别",
            "usage": "通用"
        }]
    
    # 构建话题简述
    topic_desc = f"关于「{topic}」的讨论，近期热度上升，多位创作者在跟进"
    
    # 构建金句文本
    gold_text = "\n".join([
        f"{i+1}. 「{s.get('text', '')}」— {s.get('source', '未识别')}（{s.get('speaker', '未识别')}）"
        for i, s in enumerate(gold_sentences[:3])
    ])
    
    if content_type == "thread":
        return generate_twitter_thread(topic, topic_desc, gold_text, line_count, use_llm)
    elif content_type == "xiaohongshu":
        return generate_xiaohongshu(topic, topic_desc, gold_text, use_llm)
    elif content_type == "article":
        return generate_article_outline(topic, topic_desc, gold_text, use_llm)
    else:
        return f"⚠️ 不支持的内容格式：{content_type}"


def generate_twitter_thread(topic: str, topic_desc: str, gold_text: str, line_count: int, use_llm: bool) -> str:
    """生成Twitter Thread"""
    if use_llm:
        try:
            from viewpoint_extractor import call_llm
            
            prompt = THREAD_PROMPT.format(
                line_count=line_count,
                total=line_count,
                topic=topic,
                topic_desc=topic_desc,
                gold_sentences=gold_text
            )
            
            response = call_llm(prompt)
            tweets = parse_thread_response(response, line_count)
            
            return format_thread(tweets)
            
        except Exception as e:
            print(f"⚠️ LLM调用失败: {e}")
    
    # 备选：简单规则生成
    return generate_thread_rule(topic, line_count)


def generate_xiaohongshu(topic: str, topic_desc: str, gold_text: str, use_llm: bool) -> str:
    """生成小红书文案"""
    if use_llm:
        try:
            from viewpoint_extractor import call_llm
            
            prompt = XIAOHONGSHU_PROMPT.format(
                topic=topic,
                topic_desc=topic_desc,
                gold_sentences=gold_text
            )
            
            response = call_llm(prompt)
            data = parse_xiaohongshu_response(response)
            
            return format_xiaohongshu(data)
            
        except Exception as e:
            print(f"⚠️ LLM调用失败: {e}")
    
    return "⚠️ LLM未启用或调用失败"


def generate_article_outline(topic: str, topic_desc: str, gold_text: str, use_llm: bool) -> str:
    """生成文章大纲"""
    if use_llm:
        try:
            from viewpoint_extractor import call_llm
            
            prompt = ARTICLE_OUTLINE_PROMPT.format(
                topic=topic,
                topic_desc=topic_desc,
                gold_sentences=gold_text
            )
            
            response = call_llm(prompt)
            outline = parse_article_outline(response)
            
            return format_article_outline(outline)
            
        except Exception as e:
            print(f"⚠️ LLM调用失败: {e}")
    
    return "⚠️ LLM未启用或调用失败"


def generate_thread_rule(topic: str, line_count: int = 5) -> str:
    """用规则生成Thread（备选方案）"""
    tweets = [
        f"【Tweet 1/{line_count}】",
        f"最近「{topic}」这个话题讨论得很火，",
        "我有几个观点想说说。",
        "",
        f"【Tweet 2/{line_count}】",
        f"关于「{topic}」，最核心的一点是：",
        "很多人理解错了方向。",
        "",
        f"【Tweet 3/{line_count}】",
        "具体来说：",
        "第一，XXX",
        "第二，XXX",
        "",
        f"【Tweet {line_count-1}/{line_count}】",
        "所以我的建议是：",
        "不要看别人怎么说，要看别人怎么做。",
        "",
        f"【Tweet {line_count}/{line_count}】",
        "如果你觉得有道理，转发让更多人看到。",
        "也欢迎评论区说说你的看法～",
    ]
    
    return format_thread(tweets)


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("🧪 测试Thread生成...\n")
    
    test_topic = "AI Agent创业"
    test_sentences = [
        {
            "text": "AI不会取代你，但会用AI的人会取代你",
            "source": "某科技播客",
            "speaker": "李开复",
            "usage": "适合做观点类短视频开头"
        },
        {
            "text": "Agent的下一步不是更聪明，是更听话",
            "source": "某投资人手记",
            "speaker": "未识别",
            "usage": "适合做深度分析内容"
        }
    ]
    
    print(f"话题：{test_topic}")
    print(f"金句数：{len(test_sentences)}\n")
    
    result = generate_thread(test_topic, test_sentences, line_count=5, content_type="thread", use_llm=False)
    
    print("=" * 60)
    print("生成结果：")
    print("=" * 60)
    print(result)
