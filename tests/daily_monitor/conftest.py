"""daily_monitor 测试共享 fixtures。"""

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def tmp_watchlist_path(tmp_path) -> Path:
    """空 watchlist.json 路径（文件不存在，测试自行创建）。"""
    return tmp_path / "watchlist.json"


@pytest.fixture
def sample_watchlist_data() -> dict:
    """完整的 watchlist 数据样本（含 thresholds / positions / recommended）。"""
    return {
        "version": 1,
        "thresholds": {
            "price_change_daily_pct": 5.0,
            "price_change_5d_pct": 10.0,
            "cost_drawdown_pct": 15.0,
            "pe_undervalued": 8,
            "pe_overvalued": 20,
            "dividend_yield_high": 5.0,
            "dividend_yield_low": 3.0,
            "snapshot_history_days": 30,
        },
        "positions": [
            {
                "code": "600519",
                "name": "贵州茅台",
                "buy_price": 1680.0,
                "shares": 100,
                "buy_date": "2026-03-15",
                "added_at": "2026-03-15",
            }
        ],
        "recommended": [
            {
                "code": "600036",
                "name": "招商银行",
                "first_recommended_date": "2026-07-04",
                "score_at_recommend": 4,
                "still_recommended": True,
                "last_checked_date": "2026-07-08",
            }
        ],
    }


@pytest.fixture
def sample_watchlist_file(tmp_watchlist_path, sample_watchlist_data) -> Path:
    """已写入样本数据的 watchlist.json 路径。"""
    tmp_watchlist_path.write_text(
        json.dumps(sample_watchlist_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return tmp_watchlist_path
