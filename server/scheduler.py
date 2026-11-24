# -*- coding: utf-8 -*-
"""定时任务入口：每日 07:30 触发 run_daily.py。
- Linux 服务器：用系统 cron，见 README。
- 跨平台/本地：APScheduler 常驻进程（python scheduler.py）。
- WorkBuddy 定时任务：直接每天调用 `python run_daily.py`。
"""
import subprocess
import sys
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

ROOT = os.path.dirname(os.path.abspath(__file__))


def daily_job():
    print("[scheduler] 触发每日采集", flush=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "run_daily.py")], cwd=ROOT)


def main():
    sched = BlockingScheduler(timezone="Asia/Shanghai")
    sched.add_job(daily_job, CronTrigger(hour=7, minute=30), id="daily", replace_existing=True)
    print("[scheduler] 已启动，每日 07:30 执行（Ctrl+C 退出）")
    sched.start()


if __name__ == "__main__":
    main()
