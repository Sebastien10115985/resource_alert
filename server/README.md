# 服务端（M1 骨架）

## 目录结构
```
server/
├── config.yaml          # 所有阈值/开关/推送密钥占位（改配置不改代码）
├── requirements.txt
├── common.py            # 统一 Schema(Listing)、数值解析、配置加载
├── run_daily.py         # 每日主流程：采集→评分→入库→优选→推送
├── scheduler.py         # APScheduler 定时（每日 07:30）
├── collectors/          # 采集器：land_market / mining / ejy + filter(已成交过滤)
├── pipeline/            # classifier / scorer(旧) / value_scorer(v2) / selector / notifier
├── db/store.py          # SQLite 存储 + 变更检测 + 旧库迁移
├── rescore.py           # 用当前算法重算全库分数并回写（不重新采集）
├── api/main.py          # FastAPI，供 App 拉取
├── api/admin.py         # 后台数据查看页（/admin）+ 只读 API
└── data/listings.db     # 运行后生成
```

## 虚拟环境（重要：本机已有多个 Python 项目）

本项目依赖**只装在 `server/.venv` 里**，不污染系统 Python，也不影响你其他项目。
当前 `.venv` 基于本机 Python **3.11.6** 创建（`C:\Users\lvhe\AppData\Local\Programs\Python\Python311\python.exe`）。

首次创建（若 `.venv` 已存在可跳过）：

```bash
cd server
"/c/Users/lvhe/AppData/Local/Programs/Python/Python311/python.exe" -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

日常使用两种方式，任选其一：

**方式 A — 先激活（推荐交互调试）**

- **PowerShell（你的默认终端）**：先 `cd` 到 `server`，再执行 `.ps1`
  ```powershell
  cd C:\kwg\resource_alert\server
  .\.venv\Scripts\Activate.ps1
  python --version     # 应显示 3.11.6
  ```
  > 注意：PowerShell 里**不要**执行 `activate.bat`——那是 CMD 用的，会报「无法加载模块 venv」。

- **Git Bash**：
  ```bash
  cd /c/kwg/resource_alert/server
  source .venv/Scripts/activate
  ```

- **CMD**：
  ```bat
  cd C:\kwg\resource_alert\server
  .venv\Scripts\activate.bat
  ```

**方式 B — 不激活，直接调 venv 里的解释器（推荐脚本/定时任务）**
```bash
cd server
./.venv/Scripts/python.exe run_daily.py --dry --no-push
```

## 快速开始（已激活 venv 后）

```bash
cd server

# 1) 只重算优选（不采集、不推送）——用已有数据直接验证流程
python run_daily.py --dry --no-push

# 2) 完整采集一次（约 1-3 分钟，含详情页），不推送
python run_daily.py --no-push

# 3) 启动 API（另开一个终端，同样先激活 venv）
python -m uvicorn api.main:app --port 8000
# 浏览器打开 http://localhost:8000/docs 看接口
# 浏览器打开 http://localhost:8000/admin 看人类可读的数据后台
```

> 不激活 venv 时，把所有 `python` 换成 `.venv/Scripts/python.exe` 即可。

## 后台数据查看页（/admin）

API 服务启动后，浏览器访问 **http://localhost:8000/admin** ，后台维护人员可直接以表格方式查阅采集数据，无需懂 JSON：

- **总览**：标的总数、B/C 分类数、变更数、最近优选日期；来源分布和评分分布条形图
- **标的库**：按标题/卖方/ID 搜索，按来源、分类、最低评分筛选，按评分/时间/价格排序，20 条/页翻页
- **每日优选**：按日期和 B/C 分类查看 Top-N，含排名、评分、评分理由
- **变更记录**：价格/截止时间/状态变动历史
- **详情弹窗**：全字段查看、评分理由标签、原网页链接

该页面是**只读**的，不影响 App 使用的接口；配套 API 前缀为 `/api/admin/`（overview / listings / recommendations / changes）。

## 评分算法 v2（性价比 / 风险）

`config.yaml` 的 `value_scoring.enabled: true` 时启用 v2，把五个维度**融合成单一 score**（0-100，越高越好）：

| 维度 | 含义 | 低分条件 |
|---|---|---|
| `value` 性价比 | 挂牌价 / 市场基准 | 明显超市场价值 |
| `title` 权属清晰 | 证照、出让线索 | 无证、划拨、权属不清 |
| `risk` 安全度 | 抵押查封/债务/治理义务 | 风险线索多、二次挂牌、瑕疵 |
| `seller` 挂牌方 | 政府/国资 > 产权机构 > 企业 | 卖方不可靠 |
| `time` 时效 | 剩余挂牌时间 | 已截止、不足 3 天 |

**市场价基准**：评估价优先 → 同类城市单价中位数兜底 → 同类单价中位数 → 都没有则给中性分 50 并标注「无基准」，不虚高。

**不同类型走不同算法**：`value_scoring.profiles` 按 `asset_type`（房产/土地/矿业权/二手车/股权/债权…）配置各自的权重、风险关键词、权属关键词。矿业权无价格，权重偏向权属(0.30)和安全(0.38)；二手车/设备偏性价比(0.42)。

**重算分数**（改完配置或首次升级后）：
```bash
python rescore.py --limit 5   # 抽查前 5 条明细，调参用
python rescore.py             # 全量重算 + 回写 + 重排当日推荐
```

> 当前库 1563 条已全部重算为 v2，均分 61.2。因为多数标的缺价格/评估价，性价比只能给中性分——这是数据现实，接入更多带评估价的源后会改善。旧的 B/C 评分仍在 `pipeline/scorer.py`，把 `value_scoring.enabled` 设为 false 即可回退。

## 已成交标的不入库

出让结果公示、成交公示、中标结果等**已成交**信息对"发现机会"无价值，系统在三层过滤：

1. **采集源头**：mining 只采 `kyqcrgg/`（出让公告）和 `zrgs/`（转让公示），不采 `jggs/`（出让结果）；land_market 不采"交易结果公示"端点。
2. **采集器出口**：各采集器返回前统一过 `collectors/filter.py`，按标题关键词剔除结果类。
3. **存储兜底**：`Store.upsert_listing()` 对已成交标的直接拒写，防止其他来源/旧数据混入。

判定规则集中在 `collectors/filter.py` 的 `RESULT_PATTERNS` / `RESULT_URL_PATTERNS`，发现新的结果公示话术往里加即可。存量数据在切换时已清理（删除 109 条已成交及其变更记录）。

## 推送配置（可选）
M1 默认 `push.enabled: false`。要启用，二选一：
- 在 `config.yaml` 的 `channels` 填 Webhook/sendkey；**或**
- 用环境变量（推荐，避免密钥入库）：
  - `WECOM_BOT_WEBHOOK`（企业微信机器人）
  - `DINGTALK_BOT_WEBHOOK`（钉钉机器人）
  - `SERVERCHAN_KEY`（Server酱）
然后设 `push.enabled: true`。

## 定时任务落地（注意用 venv 的解释器）

- **WorkBuddy 定时任务（推荐）**：建一条每天 07:30 的 recurring 自动化，prompt 里写清楚用 venv：
  ```
  cd C:\kwg\resource_alert\server && .venv\Scripts\python.exe run_daily.py
  ```
- **本机 Windows 任务计划程序**：程序填 `C:\kwg\resource_alert\server\.venv\Scripts\python.exe`，参数填 `run_daily.py`，起始目录填 `C:\kwg\resource_alert\server`。
- **自有 Linux 服务器 cron**（部署时重建 venv）：
  ```
  30 7 * * * cd /path/to/server && .venv/bin/python run_daily.py >> data/cron.log 2>&1
  ```
- **本地常驻（跨平台）**：先激活 venv，再 `python scheduler.py`（进程需常开）。
- **启动 FastAPI 给 App 拉数据**：同样必须用 venv 的 python，否则会用到系统里另一套包版本。

## 与已验证脚本的关系
采集逻辑来自前两天的实测脚本（`collect_market_mnr.py`、`collect_ky.py`、`collect_ejy*.py`、`rank_ejy.py`），
本骨架把它们收敛为统一 Schema + 可复用 Adapter，字段/接口/评分规则保持一致。
老脚本仍在旧工作目录，可作为对照样本。
