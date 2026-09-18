# -*- coding: utf-8 -*-
"""
舆情分析工作台 —— 全局配置
统一管理路径、字体、观点标签、情感词典等常量，各模块从这里读取。
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COOKIE_FILE = BASE_DIR / "cookie.txt"
REPORT_DIR = BASE_DIR / "舆情报告"
DICTS_DIR = BASE_DIR / "dicts"
DEMO_DIR = BASE_DIR / "demo"
FONTS_DIR = Path("C:/Windows/Fonts")

# 中文字体文件候选（用于 wordcloud 的 font_path）
CANDIDATE_FONT_FILES = ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc"]
# matplotlib 字体名（sans-serif 优先级）
MATPLOTLIB_FONT_NAMES = ["Microsoft YaHei", "SimHei", "SimSun"]


def resolve_font_file():
    """返回一个可用的中文字体文件绝对路径，找不到返回 None。"""
    for name in CANDIDATE_FONT_FILES:
        p = FONTS_DIR / name
        if p.exists():
            return str(p)
    return None


def resolve_font_name():
    """返回 matplotlib 可用的中文字体名。"""
    return MATPLOTLIB_FONT_NAMES[0]


# 十类观点标签（键：标签名；值：触发词列表，命中越多权重越高）
OPINION_TAGS = {
    "数值膨胀": ["数值膨胀", "膨胀", "伤害溢出", "一刀秒", "战力崩坏", "超模", "核爆", "亿级", "数据崩", "伤害太高"],
    "难度":     ["难度", "太难", "卡关", "劝退", "打不过", "手残", "恶心怪", "阴间", "地狱难度", "凹不动", "坐牢"],
    "奖励":     ["奖励", "福利", "补偿", "掉落", "掉率", "保底", "出货", "白嫖", "每日", "免费"],
    "环境绑定": ["绑定", "环境", "版本", "深渊", "副本", "活动", "吃环境", "虚构叙事", "星启模式", "记忆", "欢愉", "命途"],
    "角色强度": ["强度", "人权", "人权卡", "废了", "削弱", "加强", "梯队", "专武", "命座", "金"],
    "配队":     ["配队", "阵容", "搭配", "羁绊", "组合", "辅助", "主c", "主C", "队友", "追击", "buff", "轴"],
    "逼氪":     ["逼氪", "骗氪", "氪金", "氪佬", "648", "充值", "抽卡", "限定池", "月卡"],
    "练度":     ["练度", "养成", "升级", "突破", "材料", "资源", "体力", "肝", "满星", "打满", "遗器", "叠影", "练了"],
    "攻略":     ["攻略", "教学", "心得", "打法", "流程", "测评", "强度榜", "怎么打", "配队思路", "0T", "凹", "凹分", "满星攻略"],
    "二创":     ["二创", "同人", "整活", "梗", "剪辑", "cos", "手书", "mmd", "表情包"],
}

# 词频 / 词云停用词（语气词、填充词、评论常见反应词）
STOPWORDS = set(
    "回复 没有 不是 这个 那个 就是 还是 还有 其实 但是 确实 什么 一下 感觉 现在 怎么 可以 的话 "
    "这样 那样 然后 有点 真的 觉得 所以 因为 如果 一个 以及 或者 可能 应该 已经 一直 比较 不过 "
    "完全 直接 根本 居然 反而 反正 果然 毕竟 而且 大家 楼主 视频 真的 看到 知道 应该 出来 时候 "
    "doge 大哭 笑哭 哈哈 哈哈哈 阿巴 哭死 卧槽 我草 笑死 绷不住 蚌埠 有点难绷".split()
)

# 六类内容类型（键：类型名；值：触发词）
CONTENT_TYPES = {
    "吐槽": ["无语", "离谱", "恶心", "失望", "垃圾", "坑", "服了", "绷不住", "笑了", "退坑"],
    "攻略": ["攻略", "教学", "怎么打", "配队", "打法", "流程", "心得", "强度榜", "推荐"],
    "求助": ["求", "问一下", "怎么", "有没有人", "哪位大佬", "帮帮我", "请问"],
    "晒卡": ["出货", "十连", "抽到", "单抽", "欧", "晒", "运气", "一发"],
    "二创": ["二创", "同人", "整活", "剪辑", "手书", "cos", "梗图", "表情包"],
    "资讯": ["公告", "更新", "新版本", "上线", "爆料", "前瞻", "预告", "新闻"],
}

# 默认任务配置（前端未填时的兜底）
DEFAULT_CONFIG = {
    "search_mode": "keyword",        # keyword | user
    "query": "",
    "fuzzy": True,                   # 模糊检索
    "platforms": ["bilibili"],       # 目前仅实现 B 站
    "start_time": "",                # YYYY-MM-DD
    "end_time": "",
    "video_count": 20,               # 抓取视频数（默认 20）
    "comments_per_video": 1000,      # 每个视频主评论数（默认 1000）
    "capture_replies": True,         # 是否抓楼中楼
    "replies_per_comment": 50,       # 每条主评论最多抓的楼中楼条数
    "target_valid_count": 500,       # 目标有效条数
    "risk_threshold": 40,            # 负面占比高危阈值（%）
    "llm_enabled": True,
    "llm_sample_rate": 0.1,          # LLM 复核抽样比例（10%）
    "llm_base_url": "",
    "llm_api_key": "",
    "llm_model": "",
}
