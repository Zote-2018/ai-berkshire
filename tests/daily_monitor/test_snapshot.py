"""tools.daily_monitor.snapshot 单元测试。"""

from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from tools.daily_monitor.snapshot import (
    SnapshotError,
    cleanup_old_snapshots,
    load_snapshot,
    write_snapshot,
)


def _sample_snapshot(scan_date: str) -> dict:
    """构造一份快照样本。"""
    return {
        "scan_date": scan_date,
        "stocks": {
            "600036": {
                "name": "招商银行",
                "price": 38.5,
                "prev_close": 38.0,
                "pe": 7.5,
                "pb": 1.0,
                "market_cap_yi": 9700.0,
                "dividend_yield": 5.2,
                "score": 4,
            },
        },
    }


def test_write_load_往返(tmp_path):
    """写 → 读，数据一致。"""
    path = tmp_path / "snapshot-2026-07-08.json"
    snap = _sample_snapshot("2026-07-08")
    write_snapshot(snap, path)
    reloaded = load_snapshot(path)
    assert reloaded == snap


def test_load_不存在_返回None(tmp_path):
    """文件不存在时返回 None（让上游判断首次运行）。"""
    assert load_snapshot(tmp_path / "snapshot-2026-07-08.json") is None


def test_load_格式错误_抛异常(tmp_path):
    """格式错误时抛 SnapshotError。"""
    path = tmp_path / "snapshot-2026-07-08.json"
    path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(SnapshotError):
        load_snapshot(path)


def test_cleanup_保留最近N天(tmp_path):
    """保留最近 N 天，更老的删除。"""
    # 准备 5 个快照，日期跨越 10 天
    for i in range(5):
        d = f"2026-07-0{i+1}"
        path = tmp_path / f"snapshot-{d}.json"
        write_snapshot(_sample_snapshot(d), path)

    removed = cleanup_old_snapshots(tmp_path, keep_days=3, today_str="2026-07-05")
    # cutoff = 2026-07-05 - 3 days = 2026-07-02；spec：snap_date < cutoff 删除
    # → 7-01 删除；7-02（cutoff 当天）保留；7-03/04/05 保留
    assert (tmp_path / "snapshot-2026-07-01.json").exists() is False
    assert (tmp_path / "snapshot-2026-07-02.json").exists() is True
    assert (tmp_path / "snapshot-2026-07-03.json").exists() is True
    assert (tmp_path / "snapshot-2026-07-04.json").exists() is True
    assert (tmp_path / "snapshot-2026-07-05.json").exists() is True
    assert len(removed) == 1


def test_cleanup_目录不存在_不抛(tmp_path):
    """目录不存在时返回空列表，不抛异常。"""
    assert cleanup_old_snapshots(tmp_path / "nonexistent", keep_days=30, today_str="2026-07-08") == []


def test_cleanup_无snapshot文件_返回空(tmp_path):
    """目录存在但没有 snapshot-*.json 时返回空。"""
    assert cleanup_old_snapshots(tmp_path, keep_days=30, today_str="2026-07-08") == []
