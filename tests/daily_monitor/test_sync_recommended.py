"""sync_recommended 单元测试：从 stable-{date}.md 解析推荐列表并同步 watchlist。"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from tools.daily_monitor.watchlist import (
    load_watchlist, save_watchlist, sync_recommended,
)


SAMPLE_REPORT = """# 稳定收益推荐 — 2026-07-04

## Top 推荐（4 分）

| 代码 | 名称 | 股息率% | PE | ROE 均值% | ROE 标准差pp |
|---|---|---|---|---|---|
| 600036 | 招商银行 | 5.21 | 7.5 | 16.8 | 1.2 |
| 601318 | 中国平安 | 5.05 | 8.2 | 18.1 | 2.0 |

## 备选（3 分）

| 代码 | 名称 | 股息率% | PE | ROE 均值% | ROE 标准差pp |
|---|---|---|---|---|---|
| 600000 | 浦发银行 | 4.8 | 5.5 | 11.2 | 1.5 |

## fin_ai 观点层
...
"""


def test_sync_首次同步_只取4分强推荐(tmp_watchlist_path, tmp_path):
    """新推荐池：解析 4 分强推荐，忽略备选（3 分）。"""
    report_path = tmp_path / "stable-2026-07-04.md"
    report_path.write_text(SAMPLE_REPORT, encoding="utf-8")

    sync_recommended(tmp_watchlist_path, report_path, checked_date="2026-07-08")
    wl = load_watchlist(tmp_watchlist_path)

    codes = [r["code"] for r in wl["recommended"]]
    assert "600036" in codes
    assert "601318" in codes
    assert "600000" not in codes  # 3 分备选不进


def test_sync_保留历史_跌出的标记still_false(tmp_watchlist_path, tmp_path):
    """之前推荐过、本次不在 4 分列表的，标 still_recommended=False 但保留。"""
    # 先种入旧推荐
    save_watchlist({
        "version": 1,
        "thresholds": {"price_change_daily_pct": 5.0, "price_change_5d_pct": 10.0,
                       "cost_drawdown_pct": 15.0, "pe_undervalued": 8, "pe_overvalued": 20,
                       "dividend_yield_high": 5.0, "dividend_yield_low": 3.0,
                       "snapshot_history_days": 30},
        "positions": [],
        "recommended": [
            {"code": "999999", "name": "已退出股票",
             "first_recommended_date": "2026-06-01", "score_at_recommend": 4,
             "still_recommended": True, "last_checked_date": "2026-07-07"},
        ],
    }, tmp_watchlist_path)

    report_path = tmp_path / "stable-2026-07-04.md"
    report_path.write_text(SAMPLE_REPORT, encoding="utf-8")

    sync_recommended(tmp_watchlist_path, report_path, checked_date="2026-07-08")
    wl = load_watchlist(tmp_watchlist_path)

    old = next(r for r in wl["recommended"] if r["code"] == "999999")
    assert old["still_recommended"] is False
    assert old["last_checked_date"] == "2026-07-08"


def test_sync_重新进入_翻回still_true(tmp_watchlist_path, tmp_path):
    """之前跌出（still=False）、本次重新满足，翻回 still=True。"""
    save_watchlist({
        "version": 1, "thresholds": {"pe_undervalued": 8, "pe_overvalued": 20,
                                     "price_change_daily_pct": 5.0, "price_change_5d_pct": 10.0,
                                     "cost_drawdown_pct": 15.0, "dividend_yield_high": 5.0,
                                     "dividend_yield_low": 3.0, "snapshot_history_days": 30},
        "positions": [],
        "recommended": [
            {"code": "600036", "name": "招商银行",
             "first_recommended_date": "2026-06-01", "score_at_recommend": 4,
             "still_recommended": False, "last_checked_date": "2026-07-07"},
        ],
    }, tmp_watchlist_path)

    report_path = tmp_path / "stable-2026-07-04.md"
    report_path.write_text(SAMPLE_REPORT, encoding="utf-8")

    sync_recommended(tmp_watchlist_path, report_path, checked_date="2026-07-08")
    wl = load_watchlist(tmp_watchlist_path)

    rec = next(r for r in wl["recommended"] if r["code"] == "600036")
    assert rec["still_recommended"] is True
    assert rec["last_checked_date"] == "2026-07-08"
    # first_recommended_date 不变（保留首次推荐日期）
    assert rec["first_recommended_date"] == "2026-06-01"


def test_sync_报告文件不存在_抛异常(tmp_watchlist_path, tmp_path):
    """报告文件不存在时抛 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        sync_recommended(tmp_watchlist_path, tmp_path / "nonexistent.md", checked_date="2026-07-08")
