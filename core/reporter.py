# -*- coding: utf-8 -*-
"""
报告输出：生成 Markdown + Word 双格式舆情报告。
结构：监测概况 / 走势分析 / 观点总结 / 关键传播节点 / 风险研判 / 应对建议 / 附录。
"""
from pathlib import Path

import pandas as pd

import config


def _fmt_fans(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{int(v):,}"


def _fmt_dist(d):
    if not d:
        return "无"
    return "、".join(f"{k}({v})" for k, v in d.items())


def _sample_quotes(df, per_sentiment=3):
    quotes = []
    for sent in ("负", "正", "中"):
        sub = df[df["情感"] == sent]
        if sub.empty:
            continue
        for _, r in sub.head(per_sentiment).iterrows():
            quotes.append({
                "sentiment": sent,
                "name": r.get("作者昵称哈希", ""),
                "content": str(r.get("正文", ""))[:80],
                "likes": int(r.get("点赞数", 0)),
            })
    return quotes


def _risk_list(metrics, threshold):
    items = []
    neg_ratio = metrics["neg_ratio"]
    items.append(f"负面占比 {neg_ratio}%（阈值 {threshold}%）")
    # 负面集中观点
    tag_neg = metrics.get("tag_neg_top", [])
    if tag_neg:
        items.append(f"负面观点集中在：{'、'.join(tag_neg[:3])}")
    total = metrics.get("total", 0)
    if total < 100:
        items.append("样本量偏少（<100 条），结论代表性有限")
    return items


def _suggestions(metrics, threshold):
    neg_ratio = metrics["neg_ratio"]
    total = metrics.get("total", 0)
    out = []
    if neg_ratio >= threshold:
        out.append(("负面超标", "负面占比越过阈值：建议官方尽快回应争议点，发布补偿/说明公告，"
                                  "针对负面观点集中方向（如逼氪、数值膨胀）给出明确调整口径，并安排舆情监控盯后续走势。"))
    if total < 100:
        out.append(("参与不足", "声量偏低：建议加大内容投放与话题运营（攻略向/二创向内容合作、直播联动），"
                                  "用正向内容稀释负面占比，避免样本过小导致单一负面帖放大影响。"))
    # 强度党流失（观点标签中“角色强度/练度/难度”占比高且负面）
    hardcore_tags = {"角色强度", "练度", "难度", "数值膨胀"}
    tag_dist = metrics.get("tag_dist", {})
    hard_ratio = sum(tag_dist.get(t, 0) for t in hardcore_tags) / max(total, 1)
    if hard_ratio > 0.35:
        out.append(("强度党流失", "围绕强度/练度/难度的讨论占比偏高：建议关注平衡性调整与养成减负，"
                                  "避免核心强度党用户流失，必要时发布数值调整前瞻安抚。"))
    if not out:
        out.append(("常规维护", "当前舆情整体平稳：维持日常运营与内容节奏即可，持续监控拐点与突发负面。"))
    return out


def build_markdown(config_dict, metrics, df, out_dir):
    """生成 Markdown 报告内容（字符串）。"""
    m = metrics
    q = config_dict.get("query", "")
    start = config_dict.get("start_time", "") or "不限"
    end = config_dict.get("end_time", "") or "不限"
    threshold = config_dict.get("risk_threshold", 40)
    quotes = _sample_quotes(df)

    lines = []
    lines.append(f"# 舆情分析报告：{q}")
    lines.append("")
    lines.append(f"> 生成时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # 1 监测概况
    lines.append("## 一、监测概况")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("|---|---|")
    lines.append(f"| 事件主体 / 关键词 | {q} |")
    lines.append(f"| 时间窗口 | {start} ~ {end} |")
    lines.append(f"| 目标平台 | {'、'.join(config_dict.get('platforms', ['bilibili']))} |")
    lines.append(f"| 有效样本量 | {m['total']} 条 |")
    lines.append(f"| 平台分布 | {_fmt_dist(m['platform_dist'])} |")
    lines.append("")

    # 2 走势分析
    lines.append("## 二、走势分析")
    lines.append("")
    if m["timeline"]:
        peak = max(m["timeline"], key=lambda x: x[1])
        lines.append(f"声量峰值出现在 **{peak[0]}**（{peak[1]} 条）。拐点对应事件需人工补充"
                     f"（如版本更新 / 攻略视频 / 补偿公告）。")
        lines.append("")
        lines.append("| 日期 | 总声量 | 负面声量 |")
        lines.append("|---|---|---|")
        for d, t, n in m["timeline"]:
            lines.append(f"| {d} | {t} | {n} |")
        lines.append("")
    else:
        lines.append("（数据无有效时间戳，跳过时序分析。）")
        lines.append("")

    # 3 观点总结
    lines.append("## 三、观点总结")
    lines.append("")
    ed = m["emotion_dist"]
    lines.append(f"- 情感占比：正面 {ed.get('正', 0)} / 中性 {ed.get('中', 0)} / 负面 {ed.get('负', 0)}")
    lines.append(f"- 主要观点标签：{_top_tags(m['tag_dist'])}")
    lines.append(f"- 内容类型分布：{_fmt_dist(m['content_dist'])}")
    lines.append("")
    if quotes:
        lines.append("**典型言论摘录（昵称已脱敏）**：")
        lines.append("")
        for s in quotes:
            lines.append(f"- [{s['sentiment']}] {s['name']}：{s['content']}（赞 {s['likes']}）")
        lines.append("")

    # 4 关键传播节点
    lines.append("## 四、关键传播节点 Top5")
    lines.append("")
    lines.append("| # | 作者 | 粉丝数 | 点赞 | 评论 | 摘要 |")
    lines.append("|---|---|---|---|---|---|")
    for i, k in enumerate(m["key_nodes"], 1):
        lines.append(f"| {i} | {k['name_hash']} | {_fmt_fans(k['fans'])} | {k['likes']} "
                     f"| {k['rcount']} | {k['content'][:40]} |")
    lines.append("")

    # 5 风险研判
    lines.append("## 五、风险研判")
    lines.append("")
    lines.append(f"**当前风险等级：{m['risk_level']}**（负面占比 {m['neg_ratio']}%，阈值 {threshold}%）")
    lines.append("")
    lines.append("风险清单：")
    for item in _risk_list(m, threshold):
        lines.append(f"- {item}")
    lines.append("")

    # 6 应对建议
    lines.append("## 六、应对建议")
    lines.append("")
    for title, body in _suggestions(m, threshold):
        lines.append(f"**{title}**：{body}")
        lines.append("")

    # 7 附录
    lines.append("## 七、附录")
    lines.append("")
    lines.append(f"- 数据样本量：{m['total']} 条有效评论（原始数据与清洗后数据见 CSV）")
    lines.append(f"- 方法局限：情感初筛为「规则词典 + snownlp」，二者冲突及负面样本抽样 "
                 f"{config_dict.get('llm_sample_rate', 0.1) * 100:.0f}% 经 LLM 复核"
                 f"（本次 LLM 复核 {m.get('llm_checked', 0)} 条），仍有反讽/谐音误判可能。")
    lines.append("")

    text = "\n".join(lines)
    (out_dir / "report.md").write_text(text, encoding="utf-8")
    return text


def build_word(config_dict, metrics, df, out_dir):
    """生成 Word 报告（嵌入静态图）。"""
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    m = metrics
    q = config_dict.get("query", "")
    threshold = config_dict.get("risk_threshold", 40)

    doc = Document()
    doc.add_heading(f"舆情分析报告：{q}", level=0)
    doc.add_paragraph(f"生成时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")

    # 一 监测概况
    doc.add_heading("一、监测概况", level=1)
    p = doc.add_paragraph()
    p.add_run(f"事件主体 / 关键词：{q}").bold = True
    doc.add_paragraph(f"时间窗口：{config_dict.get('start_time', '') or '不限'} ~ {config_dict.get('end_time', '') or '不限'}")
    doc.add_paragraph(f"目标平台：{'、'.join(config_dict.get('platforms', ['bilibili']))}")
    doc.add_paragraph(f"有效样本量：{m['total']} 条；平台分布：{_fmt_dist(m['platform_dist'])}")

    # 二 走势分析
    doc.add_heading("二、走势分析", level=1)
    if m["timeline"]:
        peak = max(m["timeline"], key=lambda x: x[1])
        doc.add_paragraph(f"声量峰值出现在 {peak[0]}（{peak[1]} 条），拐点对应事件需人工补充。")
    else:
        doc.add_paragraph("（无有效时间戳，跳过时序分析。）")

    # 三 观点总结
    doc.add_heading("三、观点总结", level=1)
    ed = m["emotion_dist"]
    doc.add_paragraph(f"情感占比：正面 {ed.get('正', 0)} / 中性 {ed.get('中', 0)} / 负面 {ed.get('负', 0)}")
    doc.add_paragraph(f"主要观点标签：{_top_tags(m['tag_dist'])}")
    doc.add_paragraph(f"内容类型分布：{_fmt_dist(m['content_dist'])}")
    for s in _sample_quotes(df):
        doc.add_paragraph(f"[{s['sentiment']}] {s['name']}：{s['content']}")

    # 四 关键传播节点
    doc.add_heading("四、关键传播节点 Top5", level=1)
    for i, k in enumerate(m["key_nodes"], 1):
        doc.add_paragraph(f"{i}. {k['name_hash']}｜粉丝 {_fmt_fans(k['fans'])}｜赞 {k['likes']}｜"
                          f"评 {k['rcount']}｜{k['content'][:50]}")

    # 五 风险研判
    doc.add_heading("五、风险研判", level=1)
    doc.add_paragraph(f"当前风险等级：{m['risk_level']}（负面占比 {m['neg_ratio']}%，阈值 {threshold}%）")
    for item in _risk_list(m, threshold):
        doc.add_paragraph(f"• {item}", style="List Bullet")

    # 六 应对建议
    doc.add_heading("六、应对建议", level=1)
    for title, body in _suggestions(m, threshold):
        doc.add_paragraph(f"{title}：{body}")

    # 图表
    doc.add_heading("七、可视化图表", level=1)
    for png in m["pngs"]:
        if Path(png).exists():
            doc.add_picture(str(png), width=Inches(5.8))
            doc.add_paragraph("")

    # 附录
    doc.add_heading("八、附录", level=1)
    doc.add_paragraph(f"样本量：{m['total']} 条。方法局限：规则词典 + snownlp 初筛，"
                      f"冲突/负面样本抽样经 LLM 复核（本次 {m.get('llm_checked', 0)} 条），仍可能有反讽/谐音误判。")

    path = out_dir / "report.docx"
    doc.save(str(path))
    return str(path)


def _top_tags(tag_dist, n=5):
    if not tag_dist:
        return "无"
    items = sorted(tag_dist.items(), key=lambda x: -x[1])
    return "、".join(f"{k}({v})" for k, v in items[:n])


def generate_report(config_dict, metrics, df, out_dir, progress=None):
    log = progress or (lambda *a, **k: None)
    log("info", "生成 Markdown + Word 报告")
    build_markdown(config_dict, metrics, df, out_dir)
    docx_path = build_word(config_dict, metrics, df, out_dir)
    log("info", f"报告已生成：report.md / report.docx")
    return {"markdown": str(out_dir / "report.md"), "word": docx_path}
