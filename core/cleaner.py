# -*- coding: utf-8 -*-
"""
数据清洗与结构化。

流程：规整字段 → 昵称脱敏(hash) → 去重(rpid/URL/正文) → 模板文检测
     → 水军过滤(新号+高频+模板话术，剔除并单独落表) → 广告标记(不删除)
     → 提及对象抽取。
"""
import hashlib
import re
from datetime import datetime

import pandas as pd

import config

LINK_RE = re.compile(r"https?://|b23\.tv|BV1[0-9A-Za-z]{9}|av\d+")

HARD_AD_MARKERS = [
    "推广", "恰饭", "广告", "带货", "代练", "代充", "低价", "优惠", "上车",
    "加我", "私我", "私信", "客服", "q群", "qq群", "vx", "微信", "包过", "引流",
]

_CJK = re.compile(r"[一-鿿]")


def hash_name(name):
    """昵称脱敏：SHA256 取前 12 位，不存明文。"""
    if not name:
        return ""
    return hashlib.sha256(str(name).encode("utf-8")).hexdigest()[:12]


def _norm_text(s):
    if s is None:
        return ""
    s = re.sub(r"https?://\S+", " [链接] ", str(s))
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _load_entities():
    """从自定义词典提取名词实体（用于提及对象识别）。"""
    entities = set()
    p = config.DICTS_DIR / "custom_dict.txt"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[2] in ("n", "nr", "ns", "nz"):
                entities.add(parts[0])
    return entities


def clean(raw_comments, progress=None):
    """输入原始评论 list[dict]，输出 (df_clean, df_water, stats)。"""
    log = progress or (lambda *a, **k: None)
    if not raw_comments:
        raise RuntimeError("无数据可清洗（抓取结果为空，请检查关键词/时间范围）")

    df = pd.DataFrame(raw_comments)

    # ---- 字段规整 ----
    df["平台"] = df.get("platform", "bilibili")
    df["时间"] = pd.to_datetime(df.get("ctime"), unit="s", errors="coerce")
    df["正文"] = df.get("content", "").fillna("").astype(str)
    # 在链接脱敏前先检测原始链接（软广「挂链接」信号）
    df["_has_link_raw"] = df["正文"].str.contains(LINK_RE, na=False)
    df["正文"] = df["正文"].apply(_norm_text)
    df["作者昵称哈希"] = df.get("author_name", "").fillna("").map(hash_name)
    df["作者等级"] = pd.to_numeric(df.get("author_level"), errors="coerce").fillna(0).astype(int)
    df["点赞数"] = pd.to_numeric(df.get("likes"), errors="coerce").fillna(0).astype(int)
    df["rcount"] = pd.to_numeric(df.get("rcount"), errors="coerce").fillna(0).astype(int)
    df["互动数"] = df["点赞数"] + df["rcount"]
    df["作者粉丝数"] = pd.to_numeric(df.get("author_fans"), errors="coerce")
    df["是否楼中楼"] = df.get("is_reply", False).fillna(False)

    # ---- 去重 ----
    n0 = len(df)
    if "url" in df.columns:  # 预留微博/小红书 URL 去重
        df = df.drop_duplicates(subset=["url"])
    df = df.drop_duplicates(subset=["rpid"])
    df = df[df["正文"].str.len() > 0]
    df = df.drop_duplicates(subset=["正文"])
    n1 = len(df)
    log("info", f"去重完成：{n0} → {n1} 条（rpid / 正文）")

    # ---- 模板文检测（同一正文 ≥3 个不同作者发布）----
    if "author_mid" in df.columns:
        g = df.groupby("正文")["author_mid"].nunique()
        template_texts = set(g[g >= 3].index)
        df["是否模板"] = df["正文"].isin(template_texts)
    else:
        df["是否模板"] = False
    log("info", f"模板文检测：{int(df['是否模板'].sum())} 条疑似模板文案")

    # ---- 水军检测（同作者高频 + 模板/短文本）----
    df["_author_freq"] = 1
    if "author_mid" in df.columns:
        df["_author_freq"] = df.groupby("author_mid")["author_mid"].transform("size")
    short = df["正文"].str.len() <= 8
    df["是否水军"] = (df["_author_freq"] >= 5) & (df["是否模板"] | short)
    df_water = df[df["是否水军"]].copy()
    df = df[~df["是否水军"]].copy()
    log("info", f"水军过滤：剔除 {len(df_water)} 条（新号+高频+模板话术）")

    # ---- 广告标记（不删除）----
    has_link = df["_has_link_raw"].fillna(False)
    hard = df["正文"].str.contains("|".join(HARD_AD_MARKERS), na=False)
    # 软广：挂链接（URL 或「链接在简介/自取/加群」等引流话术），且非硬广
    soft_markers = ["链接在简介", "链接自取", "自取", "加群", "群里", "关注我"]
    soft_marker_hit = df["正文"].str.contains("|".join(soft_markers), na=False)
    soft = ~hard & (has_link | soft_marker_hit)
    df["广告类型"] = "无"
    df.loc[hard, "广告类型"] = "硬广"
    df.loc[soft & ~hard, "广告类型"] = "软广"
    df["是否广告"] = df["广告类型"] != "无"
    log("info", f"广告标记：硬广 {int(hard.sum())} 条，软广 {int((soft & ~hard).sum())} 条（已标记不删除）")

    # ---- 提及对象（事件主体 / 角色名，来自自定义词典 + 检索词）----
    entities = _load_entities()
    query = (df.get("_query", "") if "_query" in df.columns else "")
    if query:
        entities.update(str(query).split())

    def _mentions(t):
        return ",".join([e for e in entities if e and e in t]) or ""

    df["提及对象"] = df["正文"].apply(_mentions)

    # ---- 清理临时列 ----
    df = df.drop(columns=["_author_freq", "_has_link_raw"], errors="ignore")

    stats = {
        "原始条数": n0,
        "去重后条数": n1,
        "有效条数": int(len(df)),
        "水军剔除": int(len(df_water)),
        "广告标记": int(df["是否广告"].sum()),
        "硬广": int(hard.sum()),
        "软广": int((soft & ~hard).sum()),
    }
    log("info", f"清洗完成：有效 {stats['有效条数']} 条")
    return df, df_water, stats
