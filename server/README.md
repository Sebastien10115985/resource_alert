# 服务端（M1 骨架）

## 目录结构
```
server/
├── config.yaml          # 所有阈值/开关/推送密钥占位（改配置不改代码）
├── requirements.txt
├── common.py            # 统一 Schema(Listing)、数值解析、配置加载
├── run_daily.py         # 每日主流程：采集→评分→入库→优选→推送
├── scheduler.py         # APScheduler 定时（每日 07:30）
├── collectors/          # 采集器：land_market / mining / ejy / ggzy / rmfysszc / property_exchanges(5家产权机构) + filter + scheduler
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

- **总览**：标的总数、B/C/BC 分类数、变更数、最近优选日期；来源分布和评分分布条形图
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

> 当前库 1454 条已全部重算为 v2，均分 61.5。因为多数标的缺价格/评估价，性价比只能给中性分——这是数据现实，接入更多带评估价的源后会改善。旧的 B/C 评分仍在 `pipeline/scorer.py`，把 `value_scoring.enabled` 设为 false 即可回退。

## 分类：B / C / BC 双推

`pipeline/classifier.py` 按资产类型 + 金额判定三类（阈值 `filter.bc_threshold_wan` 默认 300 万，可调）：

| 分类 | 含义 | 判定 |
|---|---|---|
| **B** | 企业类 | 土地/矿业权/股权/债权；或房产 ≥300万 / 商业用途；或招租大额 |
| **C** | 个人类 | 二手车/二手设备/闲置资产；或普通房产 <300万；或小额招租 |
| **BC** | 双推 | 原本属 B 的大宗资产，**挂牌价有效且 ≤300万** → 企业和个人两个 Tab 都推荐 |

无价格的标的不降级为 BC（避免矿业权等无量价标的误推给个人）。BC 标的在 `recommendations` 表按 B、C 各存一条，`listings.category` 保留 `BC`，评分沿用企业的权重。改完分类规则后跑 `python rescore.py` 重算即可。

## 采集分组调度（反爬站点低频轮询）

`run_daily.py` 通过 `collectors/scheduler.py` 把数据源分两组抓取，节奏由 `config.yaml sources.<name>` 控制：

| 分组 | 配置 | 抓取节奏 |
|---|---|---|
| `open`（免爬） | `group: open` | 按注册顺序连续抓，站点间不额外等待；采集器内部仍按 `request_interval_sec` 礼貌间隔 |
| `throttled`（反爬/限流） | `group: throttled` + `cooldown_sec` + `max_attempts` | round-robin：每个站点抓一次就换下一个；**同一站点两次任务间隔 ≥ cooldown_sec**（默认 120 秒）；失败也计入冷却，最多重试 `max_attempts` 次 |

当前分组：`land_market` / `mining` / `ejy` / `rmfysszc` / `wuhan_ovupre` / `qinghai_cqjy` / `guizhou_cqjy` / `shenzhen_sotcbb` / `xiamen_cqjy` 为 open（实测无反爬）；`ggzy` 为 throttled。

**rmfysszc（人民法院诉讼资产网）已接入**：列表走 `www1` 域 `POST /News/Handler.aspx`（`www` 主域同一接口返回错误页），返回 JSON 含标题/法院/发布日期/详情链接；详情页 `www` 域静态 `.shtml` 可直连，提取起拍价/评估价/保证金/面积/权证号，金额做了空格与"万元"归一化。只保留 `fresh_days`（默认 7 天）内的公告做每日增量，配置见 `sources.rmfysszc`。实测每轮抓 60 条（3 页），有评估价的标的值得关注（折扣 0.55~0.8 能拉开性价比分）。

**第二批产权交易机构（property_exchanges.py）已接入**：武汉光谷（`GET /index/new_getxxmm.html`）、深圳联交所（`POST /api/v1/sotcbb/local/project/list`）、厦门产权（`POST /cms/article/query` + 分类树）、青海产权（GBK `/item.do` 列表）、贵州阳光（`/project/` 静态列表），实测共 201 条入库。内蒙古/新疆/黑龙江等在 `*.ejy365.com` 子站上，由 `ejy` 源覆盖不重复接。甘肃 `gscq.com.cn` 返回 403、大连/河南 zbxsoft 接口缺公开 `source` 参数，均保持人工查看不绕过。配置见 `sources.wuhan_ovupre` 等 5 节。

**ggzy 现状**：列表接口 `getTradList` 有验证码（code 829）+ 限流（code 800），直连返回 404/风控页，**不硬闯、不绕验证码**——采集器探测到风控就优雅降级返回 0 条并记录 `blocked` 原因，调度器冷却 2 分钟后重试。详情页是静态 HTML 可直连，作为后续扩展入口。

**阿里拍卖（sf/susong.taobao.com）未接入**：实测走 mtop 网关 + token 签名（`FAIL_SYS_TOKEN_EMPTY`），未登录拿不到数据；按合规原则不做签名伪造。虽有免费官方 API（`taobao.auction.gov.*`），但当前开放平台类目不含"司法拍卖"，个人开发者申请不到权限。适合人工查或未来用带登录态的浏览器渲染方案。

调度器支持注入 `now_fn`/`sleep_fn`，单元测试用假时钟验证过轮询顺序和 2 分钟冷却，无需真等。

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
