# 服务端（M1 骨架）

## 目录结构
```
server/
├── config.yaml          # 所有阈值/开关/推送密钥占位（改配置不改代码）
├── requirements.txt
├── common.py            # 统一 Schema(Listing)、数值解析、配置加载
├── run_daily.py         # 每日主流程：采集→评分→入库→优选→推送
├── scheduler.py         # APScheduler 定时（每日 07:30）
├── collectors/          # 采集器：land_market / mining / ejy
├── pipeline/            # classifier / scorer / selector / notifier
├── db/store.py          # SQLite 存储 + 变更检测
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
