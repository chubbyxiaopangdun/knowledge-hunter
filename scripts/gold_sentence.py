# -*- coding: utf-8 -*-
"""
金句提取器 v2.0
从文本中提取有价值的引用金句

金句的特征：
1. 有独特观点（不是描述，是判断）
2. 语言有力（简洁有力）
3. 可独立引用（不需要上下文）
4. 字数适中（20-80字）
5. 有共鸣感（能引发认同）
"""

import re
from typing import List, Dict, Optional


# ============================================================
# Prompt 模板
# ============================================================

EXTRACTION_PROMPT = """你是一个内容编辑。请从以下文本中提取{count}个最值得引用的金句。

提取标准（必须满足至少4条）：
1. 有独特观点 - 不是描述事实，是表达判断、洞察或主张
2. 语言有力 - 简洁有力，适合直接引用或截图
3. 独立可理解 - 不需要上下文也能完全理解
4. 长度适中 - 20-80字，太短没信息量，太长不适合引用
5. 有共鸣感 - 能引发读者的情感共鸣或认同感

【禁用】以下类型的内容不要提取：
- 纯数据罗列
- 自我介绍/头衔
- 直播/活动通知
- 感谢语/客套话
- 模糊的情绪表达（如"我觉得很好"）

输出格式（严格按此格式，每条之间用空行分隔）：
```
【金句】{完整的句子}
【来源】{视频/播客/文章的完整标题}
【发言者】{发言者的姓名，如果没有可写"未识别"}
【适用场景】{一句话说明适合做什么内容，如"适合做短视频开头引用"}
```

---
{text}
---
"""


# ============================================================
# 解析函数
# ============================================================

def parse_llm_output(text: str) -> List[Dict]:
    """
    解析LLM输出的金句列表
    
    Args:
        text: LLM返回的文本
    
    Returns:
        [{text, source, speaker, usage}, ...]
    """
    sentences = []
    
    # 匹配格式：【金句】...【来源】...【发言者】...【适用场景】...
    pattern = r'【金句】(.+?)【来源】(.+?)【发言者】(.+?)【适用场景】(.+?)(?=【金句】|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    for match in matches:
        sentences.append({
            "text": match[0].strip(),
            "source": match[1].strip(),
            "speaker": match[2].strip(),
            "usage": match[3].strip()
        })
    
    return sentences


def parse_plain_text(text: str) -> List[Dict]:
    """
    解析无格式文本（备选方案）
    
    Args:
        text: 纯文本
    
    Returns:
        [{text, source, speaker, usage}, ...]
    """
    sentences = []
    lines = text.split("\n")
    
    for line in lines:
        line = line.strip()
        # 过滤条件
        if not line:
            continue
        if len(line) < 10:
            continue
        if len(line) > 100:
            continue
        if any(char in line for char in ["@", "http", "www"]):
            continue  # 过滤链接
        
        sentences.append({
            "text": line,
            "source": "未识别",
            "speaker": "未识别",
            "usage": "适合做引用素材"
        })
    
    return sentences


# ============================================================
# 评分函数
# ============================================================

def score_sentence(sentence: str) -> float:
    """
    给句子打分，判断是否值得作为金句
    
    Returns: 0-100分
    """
    score = 50.0  # 基础分
    
    # 加分项
    positive_indicators = [
        # 有判断词（表示有观点）
        "应该", "不应该", "必须", "不能", "不是", "而是",
        "其实", "真正", "本质上", "关键", "核心", "本质",
        "最重要", "最核心", "真正", "一定", "肯定",
        # 有情绪感
        "!", "！", "竟然", "居然", "令人", "让人",
        "不得不", "毫无疑问", "毫无疑问",
        # 有数据
        r"\d+%", r"\d+万", r"\d+亿", r"\d+倍",
        # 有对比
        "而不是", "不是", "比", "与", "和",
    ]
    
    for indicator in positive_indicators:
        if re.search(indicator, sentence):
            score += 3
    
    # 减分项
    negative_indicators = [
        # 太长或太短
        (lambda s: len(s) < 10, -10),
        (lambda s: len(s) > 100, -5),
        # 太泛泛
        (lambda s: any(phrase in s for phrase in [
            "我觉得", "我觉得很好", "挺好的", "还不错",
            "谢谢大家", "感谢", "大家好"
        ]), -20),
        # 是链接或联系方式
        (lambda s: "http" in s.lower() or "www" in s.lower(), -50),
    ]
    
    for condition, penalty in negative_indicators:
        if condition(sentence):
            score += penalty
    
    return max(0, min(100, score))


def rank_sentences(sentences: List[Dict]) -> List[Dict]:
    """
    对金句列表按质量排序
    
    Args:
        sentences: 未排序的金句列表
    
    Returns:
        排序后的金句列表
    """
    for s in sentences:
        s["score"] = score_sentence(s["text"])
    
    return sorted(sentences, key=lambda x: x["score"], reverse=True)


# ============================================================
# 主函数
# ============================================================

def extract_gold_sentences(text: str, count: int = 5, use_llm: bool = True) -> List[Dict]:
    """
    提取金句的主函数
    
    Args:
        text: 要提取的文本
        count: 要提取的金句数量
        use_llm: 是否使用LLM（True优先，也可用规则作为备选）
    
    Returns:
        [{text, source, speaker, usage, score}, ...]
    """
    if not text or len(text.strip()) < 50:
        print("⚠️ 文本太短，无法提取金句")
        return []
    
    # 截断过长的文本（避免token溢出）
    max_chars = 80000
    if len(text) > max_chars:
        print(f"📄 文本较长（{len(text)}字），截断到{max_chars}字")
        text = text[:max_chars]
    
    if use_llm:
        return extract_with_llm(text, count)
    else:
        return extract_with_rules(text, count)


def extract_with_llm(text: str, count: int) -> List[Dict]:
    """
    使用LLM提取金句
    
    优先调用LLM，如果失败则使用规则提取
    """
    try:
        from viewpoint_extractor import call_llm
        
        prompt = EXTRACTION_PROMPT.format(count=count, text=text)
        response = call_llm(prompt)
        
        sentences = parse_llm_output(response)
        
        if sentences:
            print(f"✅ LLM提取成功，获得 {len(sentences)} 个金句")
            return rank_sentences(sentences)
        
    except ImportError:
        print("⚠️ viewpoint_extractor未找到，使用规则提取")
    except Exception as e:
        print(f"⚠️ LLM调用失败: {e}，使用规则提取")
    
    # LLM失败，使用规则提取
    return extract_with_rules(text, count)


def extract_with_rules(text: str, count: int) -> List[Dict]:
    """
    使用规则提取金句（备选方案）
    
    策略：
    1. 提取引号内的内容
    2. 提取感叹句/反问句
    3. 提取包含观点的短句
    """
    sentences = []
    seen = set()  # 去重
    
    # 1. 提取引号内容
    quote_patterns = [
        r'[“”「』‘’]([^“”「』‘’]{10,80})[」『”“’]',
        r'「([^」]{10,80})」',
        r'"([^"]{10,80})"',
    ]
    
    for pattern in quote_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            m = m.strip()
            if m not in seen and 10 <= len(m) <= 100:
                seen.add(m)
                sentences.append({
                    "text": m,
                    "source": "原文引用",
                    "speaker": "未识别",
                    "usage": "适合做引用素材"
                })
    
    # 2. 提取感叹句/反问句
    emphasis_patterns = [
        r'[^。！？\n]{10,60}[！？]{2,}[^。！？\n]*',  # 感叹句/反问句
        r'[^。\n]{20,60}的关键是[^。\n]*',  # 包含"关键是"
        r'[^。\n]{20,60}最重要的[^。\n]*',  # 包含"最重要的是"
        r'[^。\n]{20,60}本质上[^。\n]*',  # 包含"本质上"
    ]
    
    for pattern in emphasis_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            m = m.strip()
            if m not in seen and 10 <= len(m) <= 100:
                seen.add(m)
                sentences.append({
                    "text": m,
                    "source": "段落提炼",
                    "speaker": "未识别",
                    "usage": "适合做引用素材"
                })
    
    # 3. 提取带判断词的短句
    judgment_words = ["应该", "不应该", "必须", "不能", "不是", "而是", "真正", "关键"]
    lines = text.split("\n")
    
    for line in lines:
        line = line.strip()
        if len(line) < 15 or len(line) > 150:
            continue
        if any(word in line for word in judgment_words):
            if line not in seen:
                seen.add(line)
                sentences.append({
                    "text": line,
                    "source": "段落提炼",
                    "speaker": "未识别",
                    "usage": "适合做引用素材"
                })
    
    # 评分和排序
    ranked = rank_sentences(sentences)
    
    print(f"📝 规则提取完成，获得 {len(ranked)} 个候选，前{count}个：")
    for i, s in enumerate(ranked[:count], 1):
        print(f"   {i}. {s['text'][:50]}...")
    
    return ranked[:count]


def format_for_display(sentences: List[Dict], show_score: bool = False) -> str:
    """
    格式化金句列表用于显示
    
    Args:
        sentences: 金句列表
        show_score: 是否显示评分
    
    Returns:
        Markdown格式的文本
    """
    lines = []
    
    for i, s in enumerate(sentences, 1):
        text = s["text"]
        source = s.get("source", "未识别")
        speaker = s.get("speaker", "未识别")
        usage = s.get("usage", "适合做引用素材")
        score = s.get("score", 0)
        
        block = f"""### 💬 金句{i}

> 「{text}」

| 字段 | 内容 |
|------|------|
| 来源 | {source} |
| 发言者 | {speaker} |
| 适用场景 | {usage} |
{f"| 评分 | {score:.0f}/100 |" if show_score else ""}"""
        
        lines.append(block)
    
    return "\n\n".join(lines)


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    # 测试文本
    test_text = """
今天我想分享一个观点：真正重要的不是你怎么想，而是你怎么行动。

很多人问我，AI时代我们应该学什么？我的答案是：学会提问比学会回答更重要。

不是说你一定要学编程，而是你要理解AI能做什么、不能做什么。

关键是什么呢？关键是你要保持好奇心。保持好奇心比拥有知识更重要。

比如说，我见过很多创业者，他们失败的原因不是不够聪明，而是太聪明了。
聪明到把所有问题都想清楚了才开始行动。但真正的创新往往来自于行动中的调整。

所以我的建议是：先做，在做的过程中学习。永远不要等到准备好了再开始。
    """
    
    print("🧪 测试金句提取...")
    print(f"输入文本：{len(test_text)}字\n")
    
    sentences = extract_gold_sentences(test_text, count=5, use_llm=False)
    
    print("\n" + "=" * 60)
    print("提取结果：")
    print("=" * 60)
    print(format_for_display(sentences, show_score=True))
