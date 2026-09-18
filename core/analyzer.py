# -*- coding: utf-8 -*-
"""
量化分析：指标计算 + 图表生成。
matplotlib 出静态 PNG（嵌入 Word），pyecharts 出交互版 HTML。
"""
import math
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import config

plt.rcParams["font.sans-serif"] = config.MATPLOTLIB_FONT_NAMES
plt.rcParams["axes.unicode_minus"] = False

FONT_FILE = config.resolve_font_file()


def _cooccurrence(tokens_list, top_words, window=5):
    """滑动窗口统计 top_words 之间的共现次数。"""
    top_set = set(top_words)
    pair_count = Counter()
    for tokens in tokens_list:
        for i in range(len(tokens)):
            if tokens[i] not in top_set:
                continue
            for j in range(i + 1, min(i + window, len(tokens))):
                if tokens[j] not in top_set or tokens[j] == tokens[i]:
                    continue
                a, b = sorted([tokens[i], tokens[j]])
                pair_count[(a, b)] += 1
    return pair_count


def _emotion_png(out_dir, emotion_dist):
    labels = ["正面", "中性", "负面"]
    vals = [emotion_dist.get("正", 0), emotion_dist.get("中", 0), emotion_dist.get("负", 0)]
    colors = ["#4caf50", "#9e9e9e", "#f44336"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    axes[0].pie(vals, labels=labels, autopct="%1.1f%%", colors=colors, startangle=90)
    axes[0].set_title("情感占比（饼图）")
    axes[1].bar(labels, vals, color=colors)
    for i, v in enumerate(vals):
        axes[1].text(i, v, str(v), ha="center", va="bottom")
    axes[1].set_title("情感占比（柱状图）")
    fig.tight_layout()
    path = out_dir / "01_情感占比.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _tag_png(out_dir, tag_dist):
    items = sorted(tag_dist.items(), key=lambda x: -x[1])
    labels = [k for k, _ in items]
    vals = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(labels, vals, color="#5b8ff9")
    for i, v in enumerate(vals):
        ax.text(i, v, str(v), ha="center", va="bottom")
    ax.set_title("观点标签分布")
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    path = out_dir / "02_观点标签.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _timeline_png(out_dir, timeline):
    """timeline: list[(date_str, total, negative)]。"""
    dates = [d for d, _, _ in timeline]
    totals = [t for _, t, _ in timeline]
    negs = [n for _, _, n in timeline]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(dates, totals, marker="o", label="总声量")
    ax.plot(dates, negs, marker="s", linestyle="--", color="#f44336", label="负面声量")
    ax.set_title("声量时序（按天聚合）")
    ax.legend()
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    path = out_dir / "03_声量时序.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _wordcloud_png(out_dir, word_freq):
    from wordcloud import WordCloud
    wc = WordCloud(width=1000, height=500, background_color="white",
                   font_path=FONT_FILE, max_words=60, colormap="viridis")
    wc.generate_from_frequencies(dict(word_freq))
    path = out_dir / "04_词云.png"
    wc.to_file(path)
    return path


def _cooccur_png(out_dir, top_words, pair_count):
    """共现网络：top 词环形布局 + 边（线宽 ∝ 共现次数）。"""
    top = top_words[:20]
    n = len(top)
    pos = {}
    for i, w in enumerate(top):
        ang = 2 * math.pi * i / n
        pos[w] = (math.cos(ang), math.sin(ang))
    fig, ax = plt.subplots(figsize=(8, 8))
    max_cnt = max(pair_count.values()) if pair_count else 1
    # 边
    for (a, b), cnt in pair_count.most_common(60):
        if a not in pos or b not in pos:
            continue
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        ax.plot([x1, x2], [y1, y2], color="#cccccc", linewidth=0.5 + 3.0 * cnt / max_cnt, alpha=0.7, zorder=1)
    # 节点
    for w, (x, y) in pos.items():
        ax.scatter(x, y, s=120, color="#5b8ff9", zorder=2)
        ax.text(x * 1.12, y * 1.12, w, ha="center", va="center", fontsize=9)
    ax.set_xlim(-1.4, 1.4)
    ax.set_ylim(-1.4, 1.4)
    ax.axis("off")
    ax.set_title("热词共现网络（线越粗共现越强）")
    fig.tight_layout()
    path = out_dir / "05_共现网络.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _platform_png(out_dir, platform_emotion):
    """分平台情感对比。platform_emotion: {平台: {正:n,中:n,负:n}}。"""
    plats = list(platform_emotion.keys())
    if len(plats) <= 1:
        return None
    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = range(len(plats))
    width = 0.25
    for i, (lab, color) in enumerate([("正", "#4caf50"), ("中", "#9e9e9e"), ("负", "#f44336")]):
        vals = [platform_emotion[p].get(lab, 0) for p in plats]
        ax.bar([xi + i * width for xi in x], vals, width, label=lab, color=color)
    ax.set_xticks([xi + width for xi in x])
    ax.set_xticklabels(plats)
    ax.legend()
    ax.set_title("分平台情感对比")
    fig.tight_layout()
    path = out_dir / "06_分平台对比.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _interactive_html(out_dir, emotion_dist, tag_dist, word_freq, timeline, pair_count, top_words):
    """pyecharts 交互版图表（单页）。"""
    try:
        from pyecharts import options as opts
        from pyecharts.charts import Bar, Graph, Line, Page, Pie, WordCloud
    except Exception:
        return None

    pie = (Pie().add("", [["正面", emotion_dist.get("正", 0)],
                          ["中性", emotion_dist.get("中", 0)],
                          ["负面", emotion_dist.get("负", 0)]])
           .set_global_opts(title_opts=opts.TitleOpts(title="情感占比"))
           .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)")))

    items = sorted(tag_dist.items(), key=lambda x: -x[1])
    bar_tag = (Bar().add_xaxis([k for k, _ in items])
               .add_yaxis("条数", [v for _, v in items])
               .set_global_opts(title_opts=opts.TitleOpts(title="观点标签分布"),
                                xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=30))))

    line = (Line().add_xaxis([d for d, _, _ in timeline])
            .add_yaxis("总声量", [t for _, t, _ in timeline])
            .add_yaxis("负面声量", [n for _, _, n in timeline])
            .set_global_opts(title_opts=opts.TitleOpts(title="声量时序（按天）")))

    wc = (WordCloud().add("", list(word_freq.items())[:80], word_size_range=[12, 60])
          .set_global_opts(title_opts=opts.TitleOpts(title="热词词云")))

    nodes = [{"name": w, "symbolSize": 20 + 60 * (word_freq.get(w, 1) / max(word_freq.values()))}
             for w in top_words[:30]]
    links = [{"source": a, "target": b, "value": cnt} for (a, b), cnt in pair_count.most_common(60)
             if a in {w for w in top_words[:30]} and b in {w for w in top_words[:30]}]
    graph = (Graph().add("", nodes, links, repulsion=1000, edge_symbol=[None, "arrow"])
             .set_global_opts(title_opts=opts.TitleOpts(title="热词共现网络")))

    page = Page(layout=Page.SimplePageLayout)
    page.add(pie, bar_tag, line, wc, graph)
    path = out_dir / "interactive.html"
    page.render(str(path))
    return path


def analyze(df, word_counter, out_dir, progress=None, risk_threshold=40):
    """执行量化分析，返回 metrics dict 与生成的文件路径。"""
    log = progress or (lambda *a, **k: None)
    out_dir.mkdir(parents=True, exist_ok=True)

    log("info", "计算情感 / 标签 / 声量 / 共现等指标")

    emotion_dist = {k: int(v) for k, v in df["情感"].value_counts().items()}
    tag_dist = {k: int(v) for k, v in df["观点标签"].value_counts().items()}
    content_dist = {k: int(v) for k, v in df["内容类型"].value_counts().items()}
    platform_dist = {k: int(v) for k, v in df["平台"].value_counts().items()}

    # 词频 Top30
    stop = config.STOPWORDS | set("的了是在有我这你就他她它们没有不都也很还和与或以及一个上下左右中到说起但就是等等".replace(" ", ""))
    word_freq = Counter({w: c for w, c in word_counter.items()
                         if w not in stop and len(w) > 1 and not w.isdigit()})
    top_words = [w for w, _ in word_freq.most_common(30)]
    word_freq_top30 = word_freq.most_common(30)

    # 声量时序（按天）
    if df["时间"].notna().any():
        daily = df.set_index("时间").resample("D").size().fillna(0).astype(int)
        daily_neg = df[df["情感"] == "负"].set_index("时间").resample("D").size().fillna(0).astype(int)
        timeline = [(d.strftime("%m-%d"), int(daily[d]), int(daily_neg[d])) for d in daily.index]
    else:
        timeline = []

    # 共现
    tokens_list = [list(tokens) for tokens in df["正文"].map(lambda t: _tokenize_only(t))]
    pair_count = _cooccurrence(tokens_list, top_words)

    # 关键传播节点 Top5（点赞 + 评论 排序）
    key_nodes = []
    for _, r in df.nlargest(5, ["互动数", "点赞数"]).iterrows():
        key_nodes.append({
            "mid": int(r.get("author_mid")) if pd.notna(r.get("author_mid")) else None,
            "name_hash": r.get("作者昵称哈希", ""),
            "fans": r.get("作者粉丝数"),
            "level": int(r.get("作者等级", 0)),
            "likes": int(r.get("点赞数", 0)),
            "rcount": int(r.get("rcount", 0)),
            "interactions": int(r.get("互动数", 0)),
            "content": str(r.get("正文", ""))[:120],
            "sentiment": r.get("情感", ""),
            "tag": r.get("观点标签", ""),
            "video_title": str(r.get("video_title", ""))[:40],
        })

    # 风险研判
    total = int(len(df))
    neg_ratio = emotion_dist.get("负", 0) / total * 100 if total else 0
    if neg_ratio >= risk_threshold:
        risk_level = "高危"
    elif neg_ratio >= risk_threshold * 0.6:
        risk_level = "关注"
    else:
        risk_level = "健康"

    # 生成图表
    pngs = [
        _emotion_png(out_dir, emotion_dist),
        _tag_png(out_dir, tag_dist),
    ]
    if timeline:
        pngs.append(_timeline_png(out_dir, timeline))
    if word_freq:
        pngs.append(_wordcloud_png(out_dir, word_freq))
    if pair_count:
        pngs.append(_cooccur_png(out_dir, top_words, pair_count))

    platform_emotion = {}
    for p in platform_dist:
        sub = df[df["平台"] == p]
        platform_emotion[p] = {k: int(v) for k, v in sub["情感"].value_counts().items()}
    p_plat = _platform_png(out_dir, platform_emotion)
    if p_plat:
        pngs.append(p_plat)

    inter_html = _interactive_html(out_dir, emotion_dist, tag_dist, word_freq, timeline, pair_count, top_words)

    log("info", f"图表生成完成：{len(pngs)} 张静态图 + 交互版 {'已生成' if inter_html else '（pyecharts 不可用，已跳过）'}")

    return {
        "emotion_dist": emotion_dist,
        "tag_dist": tag_dist,
        "content_dist": content_dist,
        "platform_dist": platform_dist,
        "platform_emotion": platform_emotion,
        "word_freq_top30": word_freq_top30,
        "timeline": timeline,
        "cooccur_top": pair_count.most_common(30),
        "key_nodes": key_nodes,
        "neg_ratio": round(neg_ratio, 2),
        "risk_level": risk_level,
        "total": total,
        "pngs": [str(p) for p in pngs],
        "interactive_html": str(inter_html) if inter_html else None,
    }


def _tokenize_only(text):
    import jieba
    return [w for w in jieba.lcut(text or "") if len(w.strip()) > 1]
