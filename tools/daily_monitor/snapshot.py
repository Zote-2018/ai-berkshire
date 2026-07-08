"""每日快照读写 + 30 天滚动清理。

快照文件名格式：snapshot-{YYYY-MM-DD}.json
路径：data/monitor/snapshot-{date}.json
内容：{scan_date, stocks: {code: {price, prev_close, pe, pb, market_cap_yi, dividend_yield, score}}}

对比类信号（价格异动、推荐池变动、52 周新高低）依赖昨日快照。
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path


class SnapshotError(Exception):
    """快照操作错误。"""


def load_snapshot(path: Path):
    """加载快照。文件不存在返回 None（首次运行）；格式错误抛 SnapshotError。"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SnapshotError(f"快照格式错误 ({path}): {e}")


def write_snapshot(data: dict, path: Path) -> None:
    """保存快照。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


_SNAPSHOT_RE = re.compile(r"^snapshot-(\d{4}-\d{2}-\d{2})\.json$")


def cleanup_old_snapshots(directory: Path, *, keep_days: int, today_str: str) -> list:
    """清理 keep_days 天前的快照。返回被删除的 Path 列表。

    directory 不存在时返回空。
    today_str: 'YYYY-MM-DD'，作为今天的参考。
    """
    if not directory.exists():
        return []
    today = datetime.strptime(today_str, "%Y-%m-%d").date()
    cutoff = today - timedelta(days=keep_days)
    removed = []
    for entry in directory.iterdir():
        m = _SNAPSHOT_RE.match(entry.name)
        if not m:
            continue
        snap_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        if snap_date < cutoff:
            entry.unlink()
            removed.append(entry)
    return removed
