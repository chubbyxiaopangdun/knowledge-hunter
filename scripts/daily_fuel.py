# -*- coding: utf-8 -*-
"""
每日创意燃料生成器 v2.0
每天早上告诉你：今天做什么内容

核心功能：
1. 从过去24小时监控的内容中提取热点话题
2. 提取可引用的金句
3. 生成一个可直接发布的短内容（Thread/小红书）
4. 推送到飞书 + 同步到 Obsidian
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

# 尝试加载配置
try:
    from config import Config
    cfg = Config()
except ImportError:
    cfg = None


# ============================================================
# 金句提取 Prompt
# ============================================================

GOLD_SENTENCE_PROMPT = """你是一个内容编辑。从以下文本中提取{count}个最值得引用的金句。

提取标准（必须全部满足）：
1. 有独特观点 - 不是描述事实，是表达判断或洞察
2. 语言有力 - 简洁有力，适合直接引用
3. 独立可理解 - 不需要上下文也能理解这句话的意思
4. 长度适中 - 20-80字，太短没信息量，太长不适合引用
5. 有共鸣感 - 能引发读者的情感共鸣或认同感

输出格式（严格按此格式，每条之间用空行分隔）：
【金句】{原文}
【来源】{视频/播客/文章标题}
【发言者】{发言者姓名，如果没有可写"未识别"}
【适用场景】{适合做什么类型的内容，如"适合做观点类短视频开头"}

---
{text}
---
"""


# ============================================================
# Thread 生成 Prompt
# ============================================================

THREAD_GENERATOR_PROMPT = """你是一个Twitter内容创作者。请基于以下素材生成1个Twitter Thread。

要求：
- 共{line_count}条推文
- 每条不超过200字（留出转发空间）
- 第1条是「钩子」- 用一个惊人的事实/观点/问题吸引人点进来
- 中间2-3条是「核心观点」- 展开你的核心论点，每条聚焦一个点
- 最后1条是「行动号召」- 让粉丝互动/转发/评论
- 所有素材必须来自「可用素材」，不要自己编造数据
- 语言风格：直接、有力、带一点情绪感

---
可用素材：

热点话题：{topic}
话题简述：{topic_desc}

可用金句：
{gold_sentences}

推荐内容格式：{content_type}
---

格式示例（严格按此格式）：
【Tweet 1/{total}】
{内容}

【Tweet 2/{total}】
{内容}

……（共{line_count}条）
"""


# ============================================================
# 主函数
# ============================================================

def load_recent_content(hours=24):
    """
    加载过去N小时的所有监控内容
    返回：[(内容文本, 来源平台, 来源标题, 时间戳), ...]
    """
    content_dir = Path("输出")
    if not content_dir.exists():
        content_dir = Path("缓存/观点库")
    
    if not content_dir.exists():
        print("⚠️ 未找到内容目录，跳过内容加载")
        return []
    
    recent_content = []
    cutoff = datetime.now() - timedelta(hours=hours)
    
    # 扫描各平台的输出目录
    for platform in ["小宇宙", "YouTube", "B站"]:
        platform_dir = content_dir / platform
        if not platform_dir.exists():
            continue
        
        for md_file in platform_dir.glob("*.md"):
            try:
                # 检查文件修改时间
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                if mtime < cutoff:
                    continue
                
                # 读取内容
                content = md_file.read_text(encoding="utf-8")
                
                # 提取正文（去掉frontmatter）
                content = strip_frontmatter(content)
                
                if content.strip():
                    recent_content.append({
                        "text": content,
                        "platform": platform,
                        "file": md_file.name,
                        "mtime": mtime
                    })
            except Exception as e:
                print(f"⚠️ 读取失败 {md_file.name}: {e}")
    
    return recent_content


def strip_frontmatter(text):
    """去掉 YAML frontmatter"""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    return text.strip()


def extract_keywords(text, top_n=20):
    """简单的关键词提取"""
    # 停用词
    stop_words = {
        "的", "是", "在", "和", "了", "有", "我", "你", "他", "她",
        "它", "这", "那", "也", "就", "都", "还", "又", "要", "会",
        "能", "可以", "一个", "没有", "不是", "我们", "他们", "什么",
        "怎么", "为什么", "如果", "因为", "所以", "但是", "而且", "或者",
        "然后", "其实", "比如说", "比如说", "比如说"
    }
    
    # 提取词组（2-4字）
    words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
    
    # 过滤停用词
    words = [w for w in words if w not in stop_words]
    
    # 统计频率
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    
    # 排序
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    
    return [w for w, _ in sorted_words[:top_n]]


def extract_hot_topics(content_list, top_n=3):
    """
    从内容中提取热点话题
    返回：[{"name": "话题名", "keywords": [...], "count": 数量, "growth": "增长%"}, ...]
    """
    all_text = "\n".join([c["text"] for c in content_list])
    keywords = extract_keywords(all_text, top_n=50)
    
    # 话题评分
    topics = []
    for kw in keywords[:30]:
        count = all_text.count(kw)
        if count >= 2:
            topics.append({
                "name": kw,
                "count": count,
                "keywords": [kw],
                "growth": f"+{(count - 1) * 50}%"  # 估算增长
            })
    
    # 按数量排序，取前N
    topics.sort(key=lambda x: x["count"], reverse=True)
    
    return topics[:top_n]


def extract_gold_sentences(text, count=5, use_llm=True):
    """
    提取金句
    如果use_llm=True，调用LLM；否则用启发式规则
    """
    if use_llm:
        return extract_gold_sentences_llm(text, count)
    else:
        return extract_gold_sentences_rule(text, count)


def extract_gold_sentences_llm(text, count=5):
    """用LLM提取金句"""
    # 截断太长的文本
    if len(text) > 50000:
        text = text[:50000] + "\n……（内容过长，已截断）"
    
    prompt = GOLD_SENTENCE_PROMPT.format(count=count, text=text)
    
    # 尝试调用LLM
    try:
        from viewpoint_extractor import call_llm
        response = call_llm(prompt)
        return parse_gold_sentences(response, count)
    except Exception as e:
        print(f"⚠️ LLM调用失败，使用规则提取: {e}")
        return extract_gold_sentences_rule(text, count)


def parse_gold_sentences(text, count=5):
    """解析LLM输出的金句"""
    sentences = []
    
    # 解析格式：【金句】...【来源】...【发言者】...【适用场景】...
    pattern = r'【金句】(.+?)【来源】(.+?)【发言者】(.+?)【适用场景】(.+?)(?=【金句】|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    for match in matches[:count]:
        sentences.append({
            "text": match[0].strip(),
            "source": match[1].strip(),
            "speaker": match[2].strip(),
            "usage": match[3].strip()
        })
    
    # 如果解析失败，尝试简单分割
    if not sentences:
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if line and len(line) >= 10 and len(line) <= 100:
                sentences.append({
                    "text": line,
                    "source": "未识别",
                    "speaker": "未识别",
                    "usage": "适合做引用素材"
                })
            if len(sentences) >= count:
                break
    
    return sentences[:count]


def extract_gold_sentences_rule(text, count=5):
    """用规则提取金句（备选方案）"""
    sentences = []
    
    # 提取引号内容
    quotes = re.findall(r'[""「」(（]([^""「」（））]{10,80})[」"")）]', text)
    
    # 提取感叹句/反问句（通常是金句）
    exclamations = re.findall(r'[^。！？]*[！？]{2,}[^。！？]*', text)
    
    # 合并
    for q in quotes[:count * 2]:
        if len(q) >= 10:
            sentences.append({
                "text": q.strip(),
                "source": "未识别",
                "speaker": "未识别",
                "usage": "适合做引用素材"
            })
    
    return sentences[:count]


def generate_thread(topic, topic_desc, gold_sentences, line_count=5, use_llm=True):
    """生成Twitter Thread"""
    if use_llm:
        return generate_thread_llm(topic, topic_desc, gold_sentences, line_count)
    else:
        return generate_thread_rule(topic, gold_sentences, line_count)


def generate_thread_llm(topic, topic_desc, gold_sentences, line_count=5):
    """用LLM生成Thread"""
    gold_text = "\n".join([
        f"- {s['text']}（来自：{s['source']}）" 
        for s in gold_sentences[:3]
    ])
    
    prompt = THREAD_GENERATOR_PROMPT.format(
        line_count=line_count,
        total=line_count,
        topic=topic,
        topic_desc=topic_desc,
        gold_sentences=gold_text,
        content_type="Twitter Thread"
    )
    
    try:
        from viewpoint_extractor import call_llm
        response = call_llm(prompt)
        return response.strip()
    except Exception as e:
        print(f"⚠️ LLM调用失败: {e}")
        return generate_thread_rule(topic, gold_sentences, line_count)


def generate_thread_rule(topic, gold_sentences, line_count=5):
    """用规则生成Thread（备选方案）"""
    lines = [f"【Tweet 1/{line_count}】"]
    lines.append(f"关于「{topic}」，我有10分钟想说的。")
    
    for i, s in enumerate(gold_sentences[:line_count - 2], 2):
        lines.append(f"【Tweet {i}/{line_count}】")
        lines.append(f"「{s['text']}」")
    
    lines.append(f"【Tweet {line_count}/{line_count}】")
    lines.append("如果你也觉得有道理，转发让更多人看到。")
    
    return "\n\n".join(lines)


def assemble_fuel(hot_topics, gold_sentences, daily_thread, stats):
    """组装每日创意燃料报告"""
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    # 构建热点话题部分
    topics_section = []
    for i, topic in enumerate(hot_topics, 1):
        angles = [
            f"切入角度{i}：从「{topic['name']}」{['的用户视角', '的商业视角', '的技术视角'][i % 3]}展开",
        ]
        topics_section.append(f"""
### {i}️⃣ {topic['name']}
- 📊 热度评分：{min(85, 50 + topic['count'] * 5)}/100 | 今日相关：{topic['count']}条内容
- 🔥 为什么值得追：本周增长{topic['growth']}，多个创作者在讨论
- 💡 建议选题：「{topic['name']}的3个真相」
- ⏱️ 预估用时：25分钟 | 预计效果：中上互动
""")
    
    topics_md = "\n".join(topics_section) if topics_section else "（今日暂无明显热点，稍后再来看看）"
    
    # 构建金句部分
    sentences_md = []
    for i, s in enumerate(gold_sentences[:5], 1):
        sentences_md.append(f"""
### 💬 金句{i}
> 「{s['text']}」

- 来源：{s['source']}
- 适用：{s['usage']}
""")
    
    sentences_section = "\n".join(sentences_md) if sentences_md else "（今日暂无合适金句）"
    
    # 组装完整报告
    report = f"""# 📋 今日创意燃料 | {date_str} {weekday}

> 生成时间：{today.strftime("%H:%M")} | 数据范围：过去24小时

---

## 🔥 今日热点（{len(hot_topics)}个可追热点）

{topics_md}

---

## 💡 今日金句（{len(gold_sentences[:5])}个可直接引用的素材）

{sentences_section}

---

## ✏️ 今日可做（1个可直接发布的Thread）

**标题**：「{hot_topics[0]['name']}的3个真相」

**格式**：Twitter Thread（{line_count}条）

**内容**：

{daily_thread}

**预估效果**：中等互动，适合下午发布测试

---

## 📊 数据看板

| 指标 | 今日 | 趋势 |
|------|------|------|
| 监控内容 | {stats.get('total_content', 0)}条 | {stats.get('content_trend', '—')} |
| 热点话题 | {len(hot_topics)}个 | {stats.get('topic_trend', '—')} |
| 可用金句 | {len(gold_sentences[:5])}句 | {stats.get('sentence_trend', '—')} |
| 生成内容 | 1个 | ✅ |

---

*📌 明日预告：关注「{hot_topics[0]['name'] if hot_topics else '待定'}」持续发酵*
"""
    
    return report


def push_to_feishu(content, chat_id=None):
    """推送到飞书"""
    try:
        from sync_to_feishu import sync_to_feishu
        
        # 生成文件名
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"每日创意燃料-{today}.md"
        
        # 推送到飞书
        sync_to_feishu(content, filename)
        print(f"✅ 已推送到飞书：{filename}")
        return True
    except Exception as e:
        print(f"⚠️ 飞书推送失败: {e}")
        return False


def sync_to_obsidian(content):
    """同步到 Obsidian"""
    try:
        from sync_to_obsidian import sync_to_obsidian
        
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"每日创意燃料-{today}.md"
        
        # frontmatter
        frontmatter = f"""---
date: {today}
type: daily-fuel
tags: [内容创作, 创意燃料, 每日]
status: new
---

"""
        full_content = frontmatter + content
        
        sync_to_obsidian(full_content, filename)
        print(f"✅ 已同步到 Obsidian：{filename}")
        return True
    except Exception as e:
        print(f"⚠️ Obsidian同步失败: {e}")
        return False


def generate_stats(content_list):
    """生成统计数据"""
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    today_count = sum(1 for c in content_list if c.get("mtime", today) >= today.replace(hour=0, minute=0, second=0))
    
    return {
        "total_content": len(content_list),
        "content_trend": "↑" if today_count > 0 else "—",
        "topic_trend": "↑" if len(content_list) > 5 else "—",
        "sentence_trend": "↑" if len(content_list) > 3 else "—",
    }


def main():
    """
    主函数：生成每日创意燃料
    """
    print("🚀 正在生成今日创意燃料...")
    
    # 1. 加载内容
    print("📥 加载最近24小时内容...")
    content_list = load_recent_content(hours=24)
    print(f"   找到 {len(content_list)} 条内容")
    
    # 2. 提取热点话题
    print("🔥 提取热点话题...")
    hot_topics = extract_hot_topics(content_list, top_n=3)
    print(f"   发现 {len(hot_topics)} 个热点话题")
    
    # 3. 提取金句
    print("💡 提取金句...")
    all_text = "\n".join([c["text"] for c in content_list])
    gold_sentences = extract_gold_sentences(all_text, count=5, use_llm=True)
    print(f"   提取 {len(gold_sentences)} 个金句")
    
    # 4. 生成Thread
    print("✏️ 生成今日Thread...")
    topic_name = hot_topics[0]["name"] if hot_topics else "今日热点"
    topic_desc = f"关于{topic_name}的讨论，本周持续发酵"
    daily_thread = generate_thread(topic_name, topic_desc, gold_sentences, line_count=5, use_llm=True)
    print("   Thread生成完成")
    
    # 5. 统计数据
    stats = generate_stats(content_list)
    
    # 6. 组装报告
    print("📝 组装报告...")
    fuel = assemble_fuel(hot_topics, gold_sentences, daily_thread, stats)
    
    # 7. 打印报告（预览）
    print("\n" + "=" * 60)
    print(fuel[:2000])
    print("=" * 60)
    
    # 8. 推送
    print("\n📤 推送中...")
    pushed = push_to_feishu(fuel)
    synced = sync_to_obsidian(fuel)
    
    if pushed or synced:
        print("\n✅ 每日创意燃料生成完成！")
    else:
        print("\n⚠️ 推送失败，但报告已生成在本地")
        # 保存到本地
        output_dir = Path("输出/每日创意燃料")
        output_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        output_file = output_dir / f"{today}.md"
        output_file.write_text(fuel, encoding="utf-8")
        print(f"   已保存到：{output_file}")
    
    return fuel


if __name__ == "__main__":
    main()
