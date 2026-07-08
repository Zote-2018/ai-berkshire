#!/usr/bin/env python3
"""daily_monitor.py — 日扫描 CLI 入口 stub。

实际实现在 tools/daily_monitor/ 包里。本文件保持兼容性：
用户可继续用 `python tools/daily_monitor.py run` 的习惯。

用法见 `python tools/daily_monitor.py --help`。
"""

import sys
from pathlib import Path

# 本文件位于 {repo_root}/tools/daily_monitor.py，需把仓库根加进 sys.path
# 才能解析 `from tools.daily_monitor.__main__ import main`
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.daily_monitor.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
