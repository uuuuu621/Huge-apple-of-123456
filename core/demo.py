# -*- coding: utf-8 -*-
"""
演示数据生成器：无 Cookie 时用合成数据跑通「清洗→分词→打标→分析→报告→归档」全流程。
数据字段与 B 站真实抓取结果一致，便于无感切换。
"""
import random
from datetime import datetime, timedelta

DEMO_QUERY = "星启模式 虚构叙事"

NICKNAMES = [
    "阿伟打电动", "夜风轻语", "老二次元了", "咕咕不咕", "像素骑士", "南墙下", "咸鱼翻身",
    "打工人小张", "键盘侠本侠", "云玩家一号", "青铜上分", "熬夜冠军", "柠檬精本精", "吃瓜群众A",
    "数据帝", "攻略姬", "肝帝老王", "白嫖怪", "氪金母猪", "路人甲", "小透明", "策划黑粉头子",
]

# 观点标签 -> 评论池 (情感, 内容类型, 文本)
POOL = {
    "逼氪": [
        ("负", "吐槽", "星启模式这波摆明逼氪，平民根本玩不起，648一个接一个"),
        ("负", "吐槽", "又是限定池，骗氪骗到脸上了，退坑"),
        ("中", "求助", "月卡党玩得下去吗？感觉有点逼氪"),
    ],
    "数值膨胀": [
        ("负", "吐槽", "数值膨胀太严重，新角色一刀秒，老角色全废了"),
        ("负", "吐槽", "战力崩坏了，这游戏数值膨胀到没法看，平民退坑"),
        ("中", "资讯", "听说下版本数值要调整，看看官方怎么说"),
    ],
    "难度": [
        ("负", "吐槽", "这难度也太劝退了，卡关卡了一晚上打不过"),
        ("负", "求助", "手残党求配队，实在打不过深渊12层"),
        ("中", "攻略", "其实难度还好，练度够了就能过"),
    ],
    "奖励": [
        ("正", "资讯", "这次补偿挺良心的，白嫖党狂喜，官方好评"),
        ("正", "晒卡", "十连出货了！这掉率比上版本良心多了"),
        ("中", "吐槽", "奖励还行吧，就是每日福利能不能加点"),
    ],
    "环境绑定": [
        ("负", "吐槽", "新环境太绑定角色了，没抽人权卡根本没法玩"),
        ("中", "攻略", "这个版本吃环境，建议优先练契合角色"),
        ("负", "吐槽", "版本一换阵容全作废，吃环境吃得太狠了"),
    ],
    "角色强度": [
        ("负", "吐槽", "新角色强度超模，老角色直接废了，平衡组在干嘛"),
        ("正", "攻略", "这角色强度是真的人权，练了不亏，强烈推荐"),
        ("中", "资讯", "强度榜更新了，这期变动挺大"),
    ],
    "配队": [
        ("中", "攻略", "这套配队思路不错，辅助配主C很舒服"),
        ("中", "求助", "求问这个阵容怎么搭配比较合理？"),
        ("正", "攻略", "按这个配队打，比我之前快多了，好用"),
    ],
    "练度": [
        ("中", "求助", "练度不够卡在突破材料了，体力完全不够肝"),
        ("负", "吐槽", "养成资源太缺了，练一个角色要肝到死"),
        ("中", "攻略", "前期练度优先拉主C，别分散资源"),
    ],
    "攻略": [
        ("正", "攻略", "星启模式保姆级攻略来了，手把手教学怎么打"),
        ("正", "攻略", "这套打法流程很清晰，跟着做稳过"),
        ("中", "资讯", "这期测评视频不错，强度榜讲得挺明白"),
    ],
    "二创": [
        ("正", "二创", "这个星启模式的二创太有梗了，笑死"),
        ("正", "二创", "同人剪辑剪得太好了，爱了爱了"),
        ("中", "二创", "整活表情包已存，就冲这个入坑"),
    ],
}

HARD_ADS = [
    "低价代练上分，加我私信详聊，包过",
    "代充648只要500，qq群：123456，上车",
    "新号福利，加我vx领首充优惠，先到先得",
]
SOFT_ADS = [
    "最近发现一个很好用的加速器，链接在简介，真的很稳",
    "这套配队我录了个视频 https://b23.tv/xxxx 大家看看",
    "攻略我发在群里了 https://b23.tv/yyyy 自取",
]


def _rand_time(now, days_ago, jitter_hours=6):
    base = now - timedelta(days=days_ago)
    return int((base + timedelta(hours=random.randint(0, jitter_hours * 4))).timestamp())


def generate(query=None, seed=None, total=260):
    """生成合成评论，字段与真实抓取一致。"""
    rng = random.Random(seed or 42)
    query = query or DEMO_QUERY
    now = datetime.now()

    comments = []
    rid = 100000
    mid_seed = 900000
    rng_mid = rng.randint(1000, 9999)

    # 主评论：按标签池抽取，时间分布在近 14 天，第 3 天是声量峰值
    prefixes = ["说实话", "有一说一", "真的", "别的不说", "讲道理", "不是我说", "讲真", "笑死", "我直说了"]
    suffixes = ["，大家怎么看", "，不吐不快", "，就这", "，懂的都懂", "，谁赞成谁反对",
                "（狗头）", "🤣", "……", "，评论区聊聊", "，不服来辩"]
    tag_keys = list(POOL.keys())
    while len(comments) < total - 15:
        tag = rng.choice(tag_keys)
        sent, ctype, text = rng.choice(POOL[tag])
        # 随机加前缀/后缀变异，保证去重后仍有足够唯一文本
        text = rng.choice(prefixes) + "，" + text + rng.choice(suffixes)
        if rng.random() < 0.3:
            text = text.replace("星启模式", rng.choice(["这游戏", "这模式", "新版本"]))
        days_ago = rng.choices([3, 1, 2, 4, 0, 5, 6, 7, 8, 9, 10, 11, 12, 13],
                               weights=[24, 10, 9, 8, 7, 6, 6, 5, 5, 4, 4, 3, 2, 2])[0]
        name = rng.choice(NICKNAMES)
        comments.append({
            "platform": "bilibili",
            "rpid": rid,
            "oid": 800000 + (rid % 20),
            "root": None,
            "is_reply": False,
            "author_mid": mid_seed + (rng.randint(0, 2000)),
            "author_name": name,
            "author_level": rng.randint(1, 6),
            "author_fans": rng.randint(0, 500000),
            "content": text,
            "likes": rng.choices([0, 1, 2, 5, 10, 20, 50, 100, 500],
                                 weights=[40, 15, 12, 10, 8, 6, 4, 3, 2])[0],
            "rcount": rng.choices([0, 1, 2, 3, 5, 8, 15, 30],
                                  weights=[50, 15, 12, 8, 6, 4, 3, 2])[0],
            "ctime": _rand_time(now, days_ago),
        })
        rid += 1

    # 模板文：同一句由 4 个不同作者发布
    template_text = "星启模式良心运营，支持官方，大家冲就完事了"
    for _ in range(4):
        comments.append({
            "platform": "bilibili", "rpid": rid, "oid": 800001, "root": None,
            "is_reply": False, "author_mid": mid_seed + (rng.randint(0, 2000)),
            "author_name": rng.choice(NICKNAMES), "author_level": rng.randint(1, 3),
            "author_fans": rng.randint(0, 100), "content": template_text,
            "likes": rng.randint(0, 3), "rcount": 0,
            "ctime": _rand_time(now, rng.randint(0, 2)),
        })
        rid += 1

    # 水军：同一作者高频短文本
    water_mid = mid_seed + 9999
    water_texts = ["支持！", "顶上去", "说得对", "赞一个", "好帖子", "牛"]
    for t in water_texts:
        comments.append({
            "platform": "bilibili", "rpid": rid, "oid": 800002, "root": None,
            "is_reply": False, "author_mid": water_mid, "author_name": "刷子机器人",
            "author_level": 0, "author_fans": 3, "content": t,
            "likes": 0, "rcount": 0, "ctime": _rand_time(now, 0, jitter_hours=1),
        })
        rid += 1

    # 广告（硬广 3 + 软广 3）
    for ad in HARD_ADS:
        comments.append({
            "platform": "bilibili", "rpid": rid, "oid": 800003, "root": None,
            "is_reply": False, "author_mid": mid_seed + rng.randint(0, 2000),
            "author_name": rng.choice(NICKNAMES), "author_level": rng.randint(0, 1),
            "author_fans": rng.randint(0, 20), "content": ad,
            "likes": 0, "rcount": 0, "ctime": _rand_time(now, rng.randint(0, 3)),
        })
        rid += 1
    for ad in SOFT_ADS:
        comments.append({
            "platform": "bilibili", "rpid": rid, "oid": 800003, "root": None,
            "is_reply": False, "author_mid": mid_seed + rng.randint(0, 2000),
            "author_name": rng.choice(NICKNAMES), "author_level": rng.randint(1, 3),
            "author_fans": rng.randint(0, 200), "content": ad,
            "likes": rng.randint(0, 5), "rcount": rng.randint(0, 3),
            "ctime": _rand_time(now, rng.randint(0, 3)),
        })
        rid += 1

    # 补充楼中楼（挂在部分主评论下）
    for c in comments[:30]:
        if rng.random() < 0.5:
            comments.append({
                "platform": "bilibili", "rpid": rid, "oid": c["oid"], "root": c["rpid"],
                "is_reply": True, "author_mid": mid_seed + rng.randint(0, 2000),
                "author_name": rng.choice(NICKNAMES), "author_level": rng.randint(1, 6),
                "author_fans": rng.randint(0, 100000),
                "content": rng.choice(["同意", "确实", "楼主说得对", "别云了", "过来人表示同意"]),
                "likes": rng.randint(0, 8), "rcount": 0, "ctime": c["ctime"] + 3600,
            })
            rid += 1

    return comments
