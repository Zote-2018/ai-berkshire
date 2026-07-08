"""tools.daily_monitor.runner 集成测试。

mock fetch_quote / fetch_financials / fetch_dividends，跑完整流程。
不真发邮件（用 --no-mail 或 monkeypatch send_mail）。
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

FIXTURES = REPO_ROOT / "tests" / "daily_monitor" / "fixtures"


from tools.daily_monitor import runner


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """隔离 watchlist / 快照 / 报告 / logs 目录到 tmp。"""
    watchlist_path = tmp_path / "watchlist.json"
    snapshot_dir = tmp_path / "snapshots"
    report_dir = tmp_path / "reports"
    log_dir = tmp_path / "logs"
    for d in (snapshot_dir, report_dir, log_dir):
        d.mkdir()
    monkeypatch.setattr(runner, "DEFAULT_WATCHLIST_PATH", watchlist_path)
    monkeypatch.setattr(runner, "DEFAULT_SNAPSHOT_DIR", snapshot_dir)
    monkeypatch.setattr(runner, "DEFAULT_REPORT_DIR", report_dir)
    monkeypatch.setattr(runner, "DEFAULT_LOG_DIR", log_dir)
    return {
        "watchlist": watchlist_path,
        "snapshots": snapshot_dir,
        "reports": report_dir,
        "logs": log_dir,
    }


def _fake_quote(code):
    data = json.loads((FIXTURES / "sample_quote.json").read_text(encoding="utf-8"))
    return data[code]


def _fake_financials(code, years=3):
    data = json.loads((FIXTURES / "sample_financials.json").read_text(encoding="utf-8"))
    return data[code]


def _fake_dividends(code):
    data = json.loads((FIXTURES / "sample_dividends.json").read_text(encoding="utf-8"))
    return data[code]


def _seed_watchlist(path, positions=None, recommended=None):
    """种入 watchlist。"""
    wl = {
        "version": 1,
        "thresholds": {
            "price_change_daily_pct": 5.0, "price_change_5d_pct": 10.0,
            "cost_drawdown_pct": 15.0, "pe_undervalued": 8, "pe_overvalued": 20,
            "dividend_yield_high": 5.0, "dividend_yield_low": 3.0,
            "snapshot_history_days": 30,
        },
        "positions": positions or [],
        "recommended": recommended or [],
    }
    path.write_text(json.dumps(wl, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_首次运行_写快照不报错(isolated_env):
    """空 watchlist，首次运行：拉数据 + 写快照 + 退出码 0。"""
    _seed_watchlist(isolated_env["watchlist"],
                    positions=[{"code": "600036", "name": "招商银行",
                                "buy_price": 38.5, "shares": 100,
                                "buy_date": "2026-03-15", "added_at": "2026-03-15"}])
    with patch("tools.daily_monitor.runner.fetch_quote", side_effect=_fake_quote), \
         patch("tools.daily_monitor.runner.fetch_financials", side_effect=_fake_financials), \
         patch("tools.daily_monitor.runner.fetch_dividends", side_effect=_fake_dividends), \
         patch("tools.daily_monitor.runner.is_holiday", return_value=False):
        result = runner.run(scan_date="2026-07-08", send_email=False)

    assert result.exit_code == 0
    # 快照已写
    snapshot = isolated_env["snapshots"] / "snapshot-2026-07-08.json"
    assert snapshot.exists()
    snap = json.loads(snapshot.read_text(encoding="utf-8"))
    assert "600036" in snap["stocks"]


def test_run_全部行情失败_退出码2(isolated_env):
    """全部股票行情失败时退出码 2，不发邮件，不写快照。"""
    _seed_watchlist(isolated_env["watchlist"],
                    positions=[{"code": "600036", "name": "招行",
                                "buy_price": 38, "shares": 100,
                                "buy_date": "2026-03-15", "added_at": "2026-03-15"}])

    def _fail(code):
        raise ConnectionError("网络故障")

    with patch("tools.daily_monitor.runner.fetch_quote", side_effect=_fail), \
         patch("tools.daily_monitor.runner.is_holiday", return_value=False):
        result = runner.run(scan_date="2026-07-08", send_email=False)

    assert result.exit_code == 2


def test_run_单只股失败_其他正常处理(isolated_env):
    """1/2 失败、1/2 成功：成功的仍写入快照。"""
    _seed_watchlist(isolated_env["watchlist"],
                    positions=[
                        {"code": "600036", "name": "招行", "buy_price": 38, "shares": 100,
                         "buy_date": "2026-03-15", "added_at": "2026-03-15"},
                        {"code": "600519", "name": "茅台", "buy_price": 1700, "shares": 100,
                         "buy_date": "2026-03-15", "added_at": "2026-03-15"},
                    ])

    def _quote_mixed(code):
        if code == "600519":
            raise ConnectionError("mock 失败")
        return _fake_quote(code)

    with patch("tools.daily_monitor.runner.fetch_quote", side_effect=_quote_mixed), \
         patch("tools.daily_monitor.runner.fetch_financials", side_effect=_fake_financials), \
         patch("tools.daily_monitor.runner.fetch_dividends", side_effect=_fake_dividends), \
         patch("tools.daily_monitor.runner.is_holiday", return_value=False):
        result = runner.run(scan_date="2026-07-08", send_email=False)

    assert result.exit_code == 0  # 部分失败仍 0
    snap = json.loads((isolated_env["snapshots"] / "snapshot-2026-07-08.json").read_text(encoding="utf-8"))
    assert "600036" in snap["stocks"]
    assert "600519" not in snap["stocks"]  # 失败的不写


def test_run_节假日_跳过且退出码0(isolated_env):
    """节假日跳过整个扫描。"""
    _seed_watchlist(isolated_env["watchlist"],
                    positions=[{"code": "600036", "name": "招行",
                                "buy_price": 38, "shares": 100,
                                "buy_date": "2026-03-15", "added_at": "2026-03-15"}])

    with patch("tools.daily_monitor.runner.is_holiday", return_value=True):
        result = runner.run(scan_date="2026-05-01", send_email=False)

    assert result.exit_code == 0
    # 没写快照
    assert not (isolated_env["snapshots"] / "snapshot-2026-05-01.json").exists()


def test_run_watchlist空_退出码4(isolated_env):
    """watchlist.json 不存在 + positions/recommended 都空 → 退出码 4。"""
    # 不调用 _seed_watchlist，让文件不存在
    isolated_env["watchlist"].unlink(missing_ok=True)
    result = runner.run(scan_date="2026-07-08", send_email=False)
    assert result.exit_code == 4


def test_run_触发信号_生成报告(isolated_env):
    """触发信号时生成 reports/日扫描/{date}.md。"""
    # 茅台 PE=22 > 20，应触发 pe_overvalued
    _seed_watchlist(isolated_env["watchlist"],
                    positions=[{"code": "600519", "name": "茅台",
                                "buy_price": 1700, "shares": 100,
                                "buy_date": "2026-03-15", "added_at": "2026-03-15"}])
    with patch("tools.daily_monitor.runner.fetch_quote", side_effect=_fake_quote), \
         patch("tools.daily_monitor.runner.fetch_financials", side_effect=_fake_financials), \
         patch("tools.daily_monitor.runner.fetch_dividends", side_effect=_fake_dividends), \
         patch("tools.daily_monitor.runner.is_holiday", return_value=False):
        result = runner.run(scan_date="2026-07-08", send_email=False)

    assert result.exit_code == 0
    assert result.triggered_count >= 1
    report = isolated_env["reports"] / "2026-07-08.md"
    assert report.exists()
    content = report.read_text(encoding="utf-8")
    assert "茅台" in content
    assert "PE" in content or "pe_overvalued" in content
