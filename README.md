# 闲置资源优选推送 App（M1 骨架）

每天遍历公开资源平台，按企业类(B)/个人类(C)筛选高性价比标的，推送给用户。
工程目录：`C:\kwg\resource_alert`

## 结构
```
resource_alert/
├── android/    # Kotlin 原生 + Jetpack Compose 展示端
└── server/     # Python 采集/评分/API/定时任务
```

## M1 状态
- ✅ 三平台采集器（土地二级市场 API / 矿业权静态页 / e交易列表+详情）
- ✅ 统一 Schema、B/C 分类、双权重评分、每日 Top-N、变更检测
- ✅ FastAPI 供 App 拉取（推荐/详情/变更/统计）
- ✅ 机器人推送（企业微信/钉钉/Server酱，按需开启）
- ✅ Android 骨架（Compose 三 Tab：每日优选 / 变更 / 我的）
- ✅ 已导入 1563 条真实数据（冷启动可看）

## 快速验证（不用 Android Studio 也能看数据）

服务端依赖装在 `server/.venv` 独立虚拟环境，不影响你本机其他 Python 项目。

PowerShell（默认终端）：
```powershell
cd C:\kwg\resource_alert\server
.\.venv\Scripts\Activate.ps1
python run_daily.py --dry --no-push      # 重算优选
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
# 浏览器打开 http://localhost:8000/docs
```
Git Bash 用 `source .venv/Scripts/activate`；PowerShell 里**不要**用 `activate.bat`（那是 CMD 的）。
不激活也可以，把 `python` 换成 `.venv\Scripts\python.exe`。

## 用 Android Studio 打开
File → Open → 选择 `C:\kwg\resource_alert\android`，等 Gradle Sync 完成，连真机/模拟器运行。
- **模拟器调试**：用 `localhost` + `adb reverse`（已设为默认）。每次启动模拟器/重连后执行一次：
  ```
  adb reverse tcp:8000 tcp:8000
  ```
  然后 `local.properties` 里保持 `api.base.url=http://localhost:8000`。
  > 原因：新版模拟器（API 37）的 `10.0.2.2` NAT 不通（TCP 卡在 SYN_SENT），故不用它。
- **真机调试**：手机与电脑同 WiFi，`local.properties` 里改为电脑局域网 IP（如 `http://192.168.1.23:8000`）；服务端要用 `--host 0.0.0.0` 启动。
- 需先启动服务端 API（见上，用 venv 的 python）。

## 详细说明
- 开发文档：`docs/idle_resource_app_dev_doc.md`
- 平台实测报告：`docs/platform_verification_report.md`
- 服务端说明：`server/README.md`
