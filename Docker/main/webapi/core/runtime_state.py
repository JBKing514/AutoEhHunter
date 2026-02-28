import threading
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler


scheduler = BackgroundScheduler(timezone=ZoneInfo("UTC"))
task_state_lock = threading.Lock()
task_state: dict[str, dict[str, Any]] = {}
task_proc_lock = threading.Lock()
task_proc_state: dict[str, dict[str, Any]] = {}

model_dl_lock = threading.Lock()
model_dl_state: dict[str, dict[str, Any]] = {}
