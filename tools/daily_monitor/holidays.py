"""节假日判断。

判断规则：
1. 周六/周日 → True（交易所不开）
2. 在 data/zh-holidays.json 的对应年份列表里 → True
3. 否则 False

文件不存在或格式错误时降级：只看周末（不阻塞扫描）。
"""

import json
from datetime import datetime
from pathlib import Path


class HolidayError(Exception):
    """节假日文件格式错误。"""


DEFAULT_HOLIDAYS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "zh-holidays.json"


def load_holidays(path: Path = None) -> dict:
    """加载节假日。返回 {year_str: set(date_str)}。

    文件不存在时返回空 dict。格式错误抛 HolidayError。
    """
    path = path or DEFAULT_HOLIDAYS_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HolidayError(f"zh-holidays.json 格式错误 ({path}): {e}")
    holidays = {}
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            holidays[key] = set(value)
    return holidays


def is_holiday(date_str: str, *, holidays_path: Path = None) -> bool:
    """判断某日是否为节假日（含周末）。"""
    # 1. 周末判断
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if dt.weekday() >= 5:  # 5=周六, 6=周日
        return True

    # 2. 节假日列表判断
    holidays = load_holidays(holidays_path)
    year = date_str[:4]
    return date_str in holidays.get(year, set())
