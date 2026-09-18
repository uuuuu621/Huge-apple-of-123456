# -*- coding: utf-8 -*-
"""
分词 + 情感 + 标签。

- jieba 分词，加载自定义词典（事件名/角色名/黑话/花名）。
- 情感：规则词典优先（负面/正面词表），snownlp 打分仅作参考分。
  规则判定 >0.6 正 / <0.4 负 / 之间中性；规则与 snownlp 冲突时规则优先。
- 观点标签：热词 + 关键词规则归入十类；内容类型归入六类。
- LLM 复核：对「规则与 snownlp 不一致」+「负面」样本抽样，识别反讽/谐音/花名。
"""
import json
import random
import re
from collections import Counter

import jieba

import config


def _load_word_list(path):
    words = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                words.add(line)
    return words


class SentimentEngine:
    def __init__(self):
        self.neg_words = _load_word_list(config.DICTS_DIR / "negative_words.txt")
        self.pos_words = _load_word_list(config.DICTS_DIR / "positive_words.txt")
        self._load_custom_dict()

    def _load_custom_dict(self):
        p = config.DICTS_DIR / "custom_dict.txt"
        if not p.exists():
            return
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            word = parts[0]
            freq = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10000
            tag = parts[2] if len(parts) > 2 else "n"
            jieba.add_word(word, freq=freq, tag=tag)

    def tokenize(self, text):
        # 停用字/标点过滤
        return [w.strip() for w in jieba.lcut(text or "")
                if w.strip() and not re.fullmatch(r"[^\w一-鿿]+", w.strip())]

    def rule_sentiment(self, text):
        """规则词典打分。单字词按分词 token 匹配，避免「差」误伤「差不多」。"""
        tokens = set(self.tokenize(text))
        neg = 0
        pos = 0
        for w in self.neg_words:
            if len(w) == 1:
                neg += 1 if w in tokens else 0
            elif w in text:
                neg += 1
        for w in self.pos_words:
            if len(w) == 1:
                pos += 1 if w in tokens else 0
            elif w in text:
                pos += 1
        if neg > pos:
            return "负", neg, pos
        if pos > neg:
            return "正", neg, pos
        return "中", neg, pos

    def snownlp_score(self, text):
        try:
            from snownlp import SnowNLP
            return float(SnowNLP(text).sentiments)
        except Exception:
            return 0.5

    def sentiment(self, text):
        """返回 (最终情感, snownlp分, 规则情感, snownlp情感)。"""
        score = self.snownlp_score(text)
        rule_label, _, _ = self.rule_sentiment(text)
        sn_label = "正" if score > 0.6 else ("负" if score < 0.4 else "中")
        label = rule_label if rule_label in ("正", "负") else sn_label
        return label, score, rule_label, sn_label

    def classify_tags(self, text):
        """返回命中观点标签列表，按命中词数降序（未命中为 ['其他']）。"""
        scored = []
        for t, kws in config.OPINION_TAGS.items():
            n = sum(1 for k in kws if k in text)
            if n:
                scored.append((n, t))
        if not scored:
            return ["其他"]
        scored.sort(key=lambda x: -x[0])
        top_n = scored[0][0]
        return [t for n, t in scored if n == top_n]

    def classify_content_type(self, text):
        for typ, kws in config.CONTENT_TYPES.items():
            if any(k in text for k in kws):
                return typ
        return "其他"

    # ---------------- LLM 复核 ----------------
    def _llm_recheck(self, text, llm):
        prompt = (
            "你是舆情分析标注员。请判断下面这条中文评论的情感、内容类型和观点标签。\n"
            "注意识别反讽、谐音、花名：例如「牢玩家」是“老玩家”的自嘲黑话、未必负面；"
            "带引号的「太良心了」可能是反讽。\n\n"
            "情感可选：正 / 中 / 负\n"
            "内容类型可选：吐槽 / 攻略 / 求助 / 晒卡 / 二创 / 资讯 / 其他\n"
            "观点标签可选：数值膨胀 / 难度 / 奖励 / 环境绑定 / 角色强度 / 配队 / 逼氪 / 练度 / 攻略 / 二创 / 其他\n\n"
            f"评论：{text}\n\n"
            "只输出 JSON，格式："
            '{"sentiment":"负","content_type":"吐槽","opinion_tag":"逼氪","reason":"..."}'
        )
        resp = llm.chat([{"role": "user", "content": prompt}], temperature=0, json_mode=True)
        m = re.search(r"\{.*\}", resp, re.S)
        obj = json.loads(m.group()) if m else {}
        return obj

    def annotate(self, df, llm=None, sample_rate=0.1, progress=None):
        """对已清洗 df 做情感/标签标注，返回 (df, word_counter, stats)。"""
        log = progress or (lambda *a, **k: None)
        texts = df["正文"].tolist()
        log("info", f"开始分词与情感标注（{len(texts)} 条）")

        rows = [self.sentiment(t) for t in texts]
        df["情感"] = [r[0] for r in rows]
        df["情感分数"] = [round(r[1], 4) for r in rows]
        df["规则情感"] = [r[2] for r in rows]
        df["snownlp情感"] = [r[3] for r in rows]

        df["观点标签"] = df["正文"].apply(lambda t: self.classify_tags(t)[0])
        df["观点标签列表"] = df["正文"].apply(self.classify_tags)
        df["内容类型"] = df["正文"].apply(self.classify_content_type)

        word_counter = Counter()
        for t in texts:
            word_counter.update(self.tokenize(t))

        # ---- LLM 复核（抽样：负面 + 规则/snownlp 不一致）----
        n_checked = 0
        df["是否LLM复核"] = False
        if llm is not None and llm.available:
            cand = df.index[
                (df["情感"] == "负") | (df["规则情感"] != df["snownlp情感"])
            ].tolist()
            n_sample = max(1, int(len(cand) * (sample_rate or 0.1)))
            n_sample = min(n_sample, len(cand), 60)
            if n_sample and cand:
                sample = random.sample(cand, n_sample)
                log("info", f"LLM 复核：从 {len(cand)} 条疑似样本中抽检 {len(sample)} 条")
                for idx in sample:
                    t = df.at[idx, "正文"]
                    try:
                        obj = self._llm_recheck(t, llm)
                    except Exception as e:
                        log("info", f"LLM 复核失败（跳过）：{e}")
                        continue
                    if obj.get("sentiment") in ("正", "中", "负"):
                        df.at[idx, "情感"] = obj["sentiment"]
                    if obj.get("content_type"):
                        df.at[idx, "内容类型"] = obj["content_type"]
                    if obj.get("opinion_tag") and obj["opinion_tag"] != "其他":
                        df.at[idx, "观点标签"] = obj["opinion_tag"]
                    df.at[idx, "是否LLM复核"] = True
                    n_checked += 1
        else:
            log("info", "未配置 LLM，跳过 LLM 复核（仅规则 + snownlp）")

        stats = {
            "情感分布": df["情感"].value_counts().to_dict(),
            "观点标签分布": df["观点标签"].value_counts().to_dict(),
            "内容类型分布": df["内容类型"].value_counts().to_dict(),
            "LLM复核条数": n_checked,
        }
        log("info", f"情感标注完成：{stats['情感分布']}")
        return df, word_counter, stats
