# -*- coding: utf-8 -*-
"""
全流程编排：环境检查 → 抓取 → 清洗 → 分词打标 → 分析 → 报告 → 归档。
emit(event, **data) 用于向前端推送进度事件（log / stage / progress / done / error）。
"""
import json
import shutil

import pandas as pd

import config
from core import analyzer, bilibili, cleaner, reporter, sentiment
from core.llm import LLMClient


def load_cookie():
    p = config.COOKIE_FILE
    if p.exists():
        cookie = p.read_text(encoding="utf-8").strip()
        cookie = "\n".join(l for l in cookie.splitlines() if l.strip() and not l.startswith("#"))
        return cookie
    return ""


def check_environment(emit=None):
    """第一步：环境准备检查。返回缺失包列表。"""
    emit = emit or (lambda *a, **k: None)
    missing = []
    for mod in ("pandas", "openpyxl", "jieba", "snownlp", "matplotlib", "wordcloud", "docx"):
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        emit("log", message=f"提示：缺少依赖 {missing}，可 `pip install {' '.join(missing)}`")
    else:
        emit("log", message="环境检查通过：pandas / openpyxl / jieba / snownlp / matplotlib / wordcloud / python-docx 就绪")
    return missing


def run_pipeline(cfg, emit):
    """执行全流程，返回 result dict。异常向上抛出，由调用方 emit('error')。"""
    keyword = (cfg.get("query") or "").strip()
    demo_mode = bool(cfg.get("demo", False))
    if not keyword and not demo_mode:
        raise RuntimeError("请填写事件主体 / 关键词")

    date_str = pd.Timestamp.now().strftime("%Y%m%d")
    safe_keyword = (keyword.replace(" ", "_")[:40]) if keyword else "演示数据"
    task_dir = config.REPORT_DIR / f"{safe_keyword}_{date_str}"
    task_dir.mkdir(parents=True, exist_ok=True)

    emit("log", message=f"任务启动：{'演示模式' if demo_mode else f'检索「{keyword}」'}")

    # 第一步：环境准备
    check_environment(emit)

    # 第二步：数据抓取
    emit("stage", stage="抓取", message="正在抓取数据…", percent=3)
    client = None
    if demo_mode:
        from core import demo
        raw = demo.generate(keyword or demo.DEMO_QUERY, seed=cfg.get("seed"))
        emit("log", message=f"演示数据生成 {len(raw)} 条（未调用真实接口）")
    else:
        cookie = load_cookie()
        if not cookie:
            raise RuntimeError("未检测到 Cookie：请在 cookie.txt 填入 B 站登录 Cookie，"
                               "或勾选「使用演示数据」快速体验")
        def _bili_progress(kind, msg, pct=None):
            if kind == "progress":
                emit("progress", stage="抓取", message=msg, percent=5 + (pct or 0) * 0.5)
            else:
                emit("log", message=msg)
        client = bilibili.BilibiliClient(cookie, progress=_bili_progress)
        raw = client.scrape(cfg, progress=_bili_progress)

    emit("stage", stage="清洗", message="数据清洗与结构化…", percent=55)
    _log = lambda kind, msg: emit("log", message=msg)  # noqa: E731
    df, df_water, clean_stats = cleaner.clean(raw, progress=_log)

    # 第四步：分词 + 情感 + 标签
    emit("stage", stage="打标", message="分词 / 情感 / 标签…", percent=68)
    engine = sentiment.SentimentEngine()
    llm = None
    if (cfg.get("llm_enabled", True) and cfg.get("llm_base_url")
            and cfg.get("llm_api_key") and cfg.get("llm_model")):
        llm = LLMClient(cfg["llm_base_url"], cfg["llm_api_key"], cfg["llm_model"])
    df, word_counter, senti_stats = engine.annotate(
        df, llm=llm, sample_rate=cfg.get("llm_sample_rate", 0.1), progress=_log)

    # 第五步：量化分析
    emit("stage", stage="分析", message="量化分析与图表生成…", percent=82)
    out_dir = task_dir / "图表"
    metrics = analyzer.analyze(df, word_counter, out_dir, progress=_log,
                               risk_threshold=int(cfg.get("risk_threshold", 40)))

    # 真实抓取时补充关键节点粉丝数
    if client is not None and not demo_mode:
        for k in metrics["key_nodes"]:
            if k.get("mid"):
                try:
                    k["fans"] = client.get_user_card(k["mid"]).get("fans")
                except Exception:
                    pass

    metrics["llm_checked"] = int(senti_stats.get("LLM复核条数", 0))
    neg_df = df[df["情感"] == "负"]
    metrics["tag_neg_top"] = (neg_df["观点标签"].value_counts().index.tolist()[:5]
                              if not neg_df.empty else [])

    # 第六步：报告输出
    emit("stage", stage="报告", message="生成 Markdown + Word 报告…", percent=93)
    rep = reporter.generate_report(cfg, metrics, df, task_dir, progress=_log)

    # 第七步：归档
    emit("stage", stage="归档", message="归档原始 / 分析 / 报告文件…", percent=97)
    df.to_csv(task_dir / "评论_清洗标注.csv", index=False, encoding="utf-8-sig")
    if not df_water.empty:
        df_water.to_csv(task_dir / "评论_水军剔除.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(raw).to_csv(task_dir / "评论_原始.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(task_dir / "分析结果.xlsx", engine="openpyxl") as w:
        df.to_excel(w, sheet_name="全量评论", index=False)
        if not df_water.empty:
            df_water.to_excel(w, sheet_name="水军剔除", index=False)
        df[df["是否广告"]].to_excel(w, sheet_name="广告", index=False)
        pd.DataFrame(df["情感"].value_counts()).to_excel(w, sheet_name="情感分布")
        pd.DataFrame(df["观点标签"].value_counts()).to_excel(w, sheet_name="观点标签分布")
        pd.DataFrame(df["内容类型"].value_counts()).to_excel(w, sheet_name="内容类型分布")
    (task_dir / "config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {
        "keyword": keyword,
        "demo": demo_mode,
        "task_dir": str(task_dir),
        "rel_dir": str(task_dir.relative_to(config.REPORT_DIR)).replace("\\", "/"),
        "total": int(metrics["total"]),
        "emotion_dist": metrics["emotion_dist"],
        "tag_dist": metrics["tag_dist"],
        "content_dist": metrics["content_dist"],
        "neg_ratio": metrics["neg_ratio"],
        "risk_level": metrics["risk_level"],
        "key_nodes": metrics["key_nodes"],
        "word_freq_top30": [list(x) for x in metrics["word_freq_top30"]],
        "cooccur_top": [[list(k), v] for k, v in metrics["cooccur_top"]],
        "timeline": [list(x) for x in metrics["timeline"]],
        "report_md": rep["markdown"],
        "report_docx": rep["word"],
        "interactive_html": metrics["interactive_html"],
        "pngs": metrics["pngs"],
        "clean_stats": clean_stats,
    }
    emit("done", result=result)
    return result
