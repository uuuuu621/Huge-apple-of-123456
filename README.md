# 舆情分析工作台

一个 B 站舆情数据的可视化分析工作台：自定义检索条件后，自动完成
**搜索 → 抓取 → 清洗 → 分词 → 打标 → 分析 → 出报告** 全流程，并实时展示进度。

## 快速开始

```bash
# 1. 安装依赖（首次）
pip install -r requirements.txt

# 2. 启动
start.bat            # 或 python app.py

# 3. 浏览器打开 http://127.0.0.1:5000
```

> 首次可勾选「使用演示数据」，无需 Cookie 即可跑通全流程、查看报告效果。

## 真实抓取（B 站）

1. 复制 `cookie.txt.example` 为 `cookie.txt`。
2. 浏览器登录 bilibili.com → F12 → 网络面板 → 复制任意 `api.bilibili.com` 请求头里的 `Cookie`，粘贴到 `cookie.txt`（需含 `SESSDATA`）。
3. 前端不勾选「使用演示数据」，填关键词执行即可。

> `cookie.txt` 已被 `.gitignore` 忽略，不会提交到 GitHub；本项目不内置任何 Cookie，请自行获取。

## 开源协议

[MIT](./LICENSE)。欢迎提 Issue / PR 一起完善多平台接入、词典与标签规则。

## 目录结构

```
舆情工作台/
├── app.py                Flask 后端（任务 + SSE 进度）
├── config.py             全局配置（字体/词典/观点标签/默认参数）
├── cookie.txt            B 站登录 Cookie（真实抓取必需）
├── workbench/index.html  前端工作台（单页）
├── core/
│   ├── bilibili.py       B 站 WBI 签名 + 搜索 + 评论抓取
│   ├── cleaner.py        清洗/去重/水军过滤/广告标记
│   ├── sentiment.py      分词 + 规则情感 + snownlp + LLM 复核
│   ├── analyzer.py       指标计算 + matplotlib/pyecharts 图表
│   ├── reporter.py       Markdown + Word 报告
│   ├── pipeline.py       全流程编排
│   ├── demo.py           演示数据生成器
│   └── llm.py            OpenAI 兼容 LLM 客户端
├── dicts/                自定义词典 / 正负面词表
└── 舆情报告/{关键词}_{日期}/   归档：原始 CSV、分析结果、图表、报告
```

## 已实现 vs 待接入

| 平台 | 状态 |
|---|---|
| B 站（视频搜索 + 主评论 + 楼中楼） | ✅ 已实现（WBI 签名） |
| 微博 / 抖音 / 小红书 | ⏳ 待接入（前端已预留选项） |

## 方法说明

- **情感**：规则词典（正/负面词表）优先，`snownlp` 打分作参考；规则与 snownlp 冲突、以及负面样本，抽样经 LLM（OpenAI 兼容接口）复核反讽/谐音/花名。
- **观点标签**：热词 + 关键词规则归入十类（数值膨胀/难度/奖励/环境绑定/角色强度/配队/逼氪/练度/攻略/二创）。
- **风控**：请求间隔 1–1.5s；遇 `-352/412` 暂停 30s 重试。
- **隐私**：用户昵称 SHA256 脱敏；Cookie 不打印到日志。
- **报告**：Markdown + Word 双格式；图表 matplotlib（静态，嵌入 Word）+ pyecharts（交互 HTML）。
