# -*- coding: utf-8 -*-
"""
B 站数据抓取：WBI 签名 + 搜索视频 + 主评论 / 楼中楼抓取。

接口说明：
  - 搜索视频：  x/web-interface/wbi/search/type  （order=click 按播放量排序）
  - 主评论：    x/v2/reply/wbi/main
  - 楼中楼：    x/v2/reply/reply
  - 用户卡片：  x/web-interface/card            （取粉丝数，仅关键节点调用）
风控策略：请求间隔 1–1.5s；遇 -352 / 412 / -412 暂停 30s 重试。
Cookie 从工作空间 cookie.txt 读取，未配置则抛错提示。
"""
import hashlib
import random
import re
import time
from urllib.parse import urlencode

import requests

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


class _RetryLater(Exception):
    """风控信号，触发 30s 暂停重试。"""


class BilibiliClient:
    def __init__(self, cookie, progress=None, sleep_range=(1.0, 1.5)):
        self.cookie = (cookie or "").strip()
        self.progress = progress or (lambda *a, **k: None)
        self.sleep_range = sleep_range
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
            "Cookie": self.cookie,
        })
        self._img_key = None
        self._sub_key = None

    # ---------------- 基础设施 ----------------
    def _log(self, msg):
        self.progress("info", msg)

    def _sleep(self):
        time.sleep(random.uniform(*self.sleep_range))

    def _ensure_wbi_keys(self):
        if self._img_key and self._sub_key:
            return
        r = self.session.get("https://api.bilibili.com/x/web-interface/nav", timeout=10)
        data = r.json()
        wbi = (data.get("data") or {}).get("wbi_img") or {}
        img_url = wbi.get("img_url", "")
        sub_url = wbi.get("sub_url", "")
        if not img_url or not sub_url:
            raise RuntimeError(
                f"获取 WBI 密钥失败（code={data.get('code')}，"
                f"msg={data.get('message')}）。请确认 cookie.txt 已填入有效登录 Cookie（需含 SESSDATA）。"
            )
        self._img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
        self._sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]

    def _mixin_key(self):
        raw = self._img_key + self._sub_key
        return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB)[:32]

    def _sign(self, params):
        params = dict(params)
        params["wts"] = int(time.time())
        params = dict(sorted(params.items()))
        query = urlencode(params)
        query = re.sub(r"[!'()*]", "", query)
        params["w_rid"] = hashlib.md5((query + self._mixin_key()).encode()).hexdigest()
        return params

    def _get(self, url, params=None, wbi=True, retries=5):
        last_err = None
        for attempt in range(retries):
            try:
                p = dict(params or {})
                if wbi:
                    self._ensure_wbi_keys()
                    p = self._sign(p)
                r = self.session.get(url, params=p, timeout=15)
                if r.status_code == 412:
                    raise _RetryLater("HTTP 412")
                data = r.json()
                code = data.get("code", 0)
                if code == 0:
                    return data
                if code in (-352, -412):
                    raise _RetryLater(f"code={code} {data.get('message')}")
                last_err = RuntimeError(f"code={code} msg={data.get('message')}")
                raise last_err  # 非风控业务错误，直接抛
            except _RetryLater as e:
                self._log(f"触发风控（{e}），暂停 30s 后重试（第 {attempt + 1}/{retries} 次）")
                time.sleep(30)
            except requests.RequestException as e:
                last_err = e
                self._log(f"网络异常：{e}，3s 后重试（第 {attempt + 1}/{retries} 次）")
                time.sleep(3)
        raise (last_err or RuntimeError("抓取失败"))

    # ---------------- 搜索 ----------------
    def search_videos(self, keyword, count=20, page_size=20):
        """按关键词搜索视频，返回按播放量排序的前 count 个。"""
        self._log(f"搜索视频关键词：「{keyword}」")
        url = "https://api.bilibili.com/x/web-interface/wbi/search/type"
        videos = []
        page = 1
        while len(videos) < count and page <= 10:
            data = self._get(url, {
                "search_type": "video",
                "keyword": keyword,
                "page": page,
                "page_size": min(page_size, 50),
                "order": "click",
            })
            result = (data.get("data") or {}).get("result") or []
            if not result:
                break
            for it in result:
                if str(it.get("type")) != "video":
                    continue
                videos.append({
                    "bvid": it.get("bvid"),
                    "aid": it.get("aid"),
                    "title": re.sub(r"<[^>]+>", "", it.get("title", "")),
                    "play": it.get("play", 0),
                    "like": it.get("like", 0),
                    "author": it.get("author", ""),
                    "pubdate": it.get("pubdate", 0),
                    "description": re.sub(r"<[^>]+>", "", it.get("description", "")),
                })
            page += 1
            self._sleep()
        videos.sort(key=lambda v: v.get("play", 0), reverse=True)
        self._log(f"搜索到 {len(videos)} 个视频，按播放量取前 {min(count, len(videos))} 个")
        return videos[:count]

    def search_user_mid(self, keyword):
        """按 UP 主名称搜索其 mid。"""
        url = "https://api.bilibili.com/x/web-interface/wbi/search/type"
        data = self._get(url, {"search_type": "bili_user", "keyword": keyword,
                               "page": 1, "page_size": 10})
        result = (data.get("data") or {}).get("result") or []
        for it in result:
            if str(it.get("type")) == "bili_user":
                return it.get("mid"), it.get("uname")
        return None, None

    def fetch_user_videos(self, mid, count=20):
        """抓取某 UP 主发布的视频列表。"""
        url = "https://api.bilibili.com/x/space/wbi/arc/search"
        videos = []
        pn = 1
        while len(videos) < count and pn <= 5:
            data = self._get(url, {"mid": mid, "ps": 30, "pn": pn, "order": "click"})
            vlist = ((data.get("data") or {}).get("list") or {}).get("vlist") or []
            if not vlist:
                break
            for it in vlist:
                videos.append({
                    "bvid": it.get("bvid"),
                    "aid": it.get("aid"),
                    "title": re.sub(r"<[^>]+>", "", it.get("title", "")),
                    "play": it.get("play", 0),
                    "like": it.get("video_review", 0),
                    "author": it.get("author", ""),
                    "pubdate": it.get("created", 0),
                    "description": "",
                })
            pn += 1
            self._sleep()
        videos.sort(key=lambda v: v.get("play", 0), reverse=True)
        return videos[:count]

    # ---------------- 评论 ----------------
    def _parse_reply(self, r, oid, is_reply=False, root=None):
        member = r.get("member") or {}
        content = r.get("content") or {}
        return {
            "platform": "bilibili",
            "rpid": r.get("rpid"),
            "oid": oid,
            "root": root,
            "is_reply": is_reply,
            "author_mid": member.get("mid"),
            "author_name": member.get("uname", ""),
            "author_level": (member.get("level_info") or {}).get("current_level")
                            or member.get("level", 0),
            "author_fans": None,  # 粉丝数需单独请求，抓取阶段置空
            "content": (content.get("message") or "").strip(),
            "likes": r.get("like", 0),
            "rcount": r.get("rcount", 0),
            "ctime": r.get("ctime", 0),
        }

    def fetch_main_comments(self, oid, max_count=1000):
        url = "https://api.bilibili.com/x/v2/reply/wbi/main"
        comments = []
        pagination_str = ""
        while len(comments) < max_count:
            data = self._get(url, {
                "type": 1, "oid": oid, "mode": 3,
                "pagination_str": pagination_str, "plat": 1, "web_location": 1315875,
            })
            d = data.get("data") or {}
            for r in (d.get("replies") or []):
                comments.append(self._parse_reply(r, oid))
            cursor = d.get("cursor") or {}
            if cursor.get("is_end", True):
                break
            pagination_str = cursor.get("pagination_str", "")
            if not pagination_str:
                break
            self._sleep()
        self._log(f"视频 {oid} 主评论抓取 {len(comments)} 条")
        return comments[:max_count]

    def fetch_replies(self, oid, root, max_count=50):
        """抓取某条主评论下的楼中楼。"""
        url = "https://api.bilibili.com/x/v2/reply/reply"
        replies = []
        pn = 1
        while len(replies) < max_count:
            data = self._get(url, {"type": 1, "oid": oid, "root": root, "ps": 20, "pn": pn})
            items = (data.get("data") or {}).get("replies") or []
            if not items:
                break
            for r in items:
                replies.append(self._parse_reply(r, oid, is_reply=True, root=root))
            pn += 1
            self._sleep()
        return replies[:max_count]

    def get_user_card(self, mid):
        """获取用户卡片（含粉丝数），仅用于关键节点补充。"""
        data = self._get("https://api.bilibili.com/x/web-interface/card", {"mid": mid})
        card = (data.get("data") or {}).get("card") or {}
        return {"mid": mid, "name": card.get("name", ""), "fans": card.get("fans")}

    # ---------------- 完整抓取 ----------------
    def scrape(self, config, progress=None):
        """按配置完整抓取，返回原始评论 list[dict]。"""
        if progress:
            self.progress = progress
        mode = config.get("search_mode", "keyword")
        query = config["query"]
        count = int(config.get("video_count", 20))

        if mode == "user":
            self._log(f"按 UP 主检索：「{query}」")
            mid, uname = self.search_user_mid(query)
            if not mid:
                raise RuntimeError(f"未找到 UP 主「{query}」，请确认名称或改用关键词检索")
            self._log(f"定位到 UP 主：{uname}（mid={mid}）")
            videos = self.fetch_user_videos(mid, count)
        else:
            videos = self.search_videos(query, count)

        videos = [v for v in videos if v.get("aid")]  # 过滤无 aid 的异常项
        if not videos:
            raise RuntimeError("未搜索到任何视频，请检查关键词 / 时间范围")

        capture_replies = bool(config.get("capture_replies", True))
        reply_limit = int(config.get("replies_per_comment", 50))
        all_comments = []
        total = len(videos)
        for i, v in enumerate(videos):
            self.progress("progress", f"[{i + 1}/{total}] 抓取《{v['title'][:30]}》评论",
                          i / total * 100)
            try:
                mains = self.fetch_main_comments(v["aid"], int(config.get("comments_per_video", 1000)))
            except Exception as e:
                self._log(f"视频 {v.get('bvid') or v.get('aid')} 主评论抓取失败：{e}")
                continue
            for c in mains:
                c.update(video_title=v["title"], video_bvid=v["bvid"], video_play=v["play"])
            all_comments.extend(mains)
            if capture_replies:
                with_reply = [c for c in mains if c["rcount"] > 0]
                for j, c in enumerate(with_reply):
                    try:
                        reps = self.fetch_replies(v["aid"], c["rpid"], reply_limit)
                    except Exception:
                        continue
                    for r in reps:
                        r.update(video_title=v["title"], video_bvid=v["bvid"], video_play=v["play"])
                    all_comments.extend(reps)
                self._log(f"视频《{v['title'][:30]}》楼中楼已抓取（{len(with_reply)} 条主评论下有回复）")
        self._log(f"抓取完成，共获得原始评论 {len(all_comments)} 条")
        return all_comments
