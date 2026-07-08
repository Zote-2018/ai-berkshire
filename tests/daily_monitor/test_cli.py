"""CLI 子命令测试（add-position / remove-position / show-watchlist / show-config）。

通过 main(argv=[...]) 直接调用，避免 subprocess 开销。
watchlist.json 路径通过 monkeypatch 替换 DEFAULT_WATCHLIST_PATH。
"""

from pathlib import Path
import json

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from tools.daily_monitor import __main__ as cli
from tools.daily_monitor import watchlist as wl_mod


@pytest.fixture
def isolated_watchlist(tmp_path, monkeypatch):
    """让 CLI 操作指向 tmp 目录的 watchlist.json。"""
    fake_path = tmp_path / "watchlist.json"
    monkeypatch.setattr(wl_mod, "DEFAULT_WATCHLIST_PATH", fake_path)
    # runner.py / __main__.py 里所有 watchlist.json 路径都通过该常量
    return fake_path


def test_cli_add_position_写入文件(isolated_watchlist):
    """CLI add-position 子命令正确写入 watchlist.json。"""
    exit_code = cli.main([
        "add-position", "600036",
        "--buy-price", "38.5",
        "--shares", "1000",
        "--buy-date", "2026-03-15",
        "--name", "招商银行",
    ])
    assert exit_code == 0
    wl = wl_mod.load_watchlist(isolated_watchlist)
    assert len(wl["positions"]) == 1
    assert wl["positions"][0]["code"] == "600036"
    assert wl["positions"][0]["buy_price"] == 38.5


def test_cli_add_position_缺name也能添加(isolated_watchlist):
    """--name 缺省时用 code 占位（后续 sync-recommended 会补真实名）。"""
    exit_code = cli.main([
        "add-position", "600036",
        "--buy-price", "38.5",
        "--shares", "1000",
        "--buy-date", "2026-03-15",
    ])
    assert exit_code == 0
    wl = wl_mod.load_watchlist(isolated_watchlist)
    assert wl["positions"][0]["name"] == "600036"


def test_cli_remove_position_正常删除(isolated_watchlist):
    """先添加再删除，结果为空。"""
    cli.main(["add-position", "600036", "--buy-price", "38.5",
              "--shares", "1000", "--buy-date", "2026-03-15", "--name", "招商银行"])
    exit_code = cli.main(["remove-position", "600036"])
    assert exit_code == 0
    wl = wl_mod.load_watchlist(isolated_watchlist)
    assert wl["positions"] == []


def test_cli_show_watchlist_打印结构(isolated_watchlist, capsys):
    """show-watchlist 输出 watchlist 内容到 stdout。"""
    cli.main(["add-position", "600036", "--buy-price", "38.5",
              "--shares", "1000", "--buy-date", "2026-03-15", "--name", "招商银行"])
    cli.main(["show-watchlist"])
    captured = capsys.readouterr()
    assert "600036" in captured.out
    assert "招商银行" in captured.out


def test_cli_show_config_打印阈值(isolated_watchlist, capsys):
    """show-config 输出 thresholds 到 stdout。"""
    cli.main(["show-config"])
    captured = capsys.readouterr()
    assert "price_change_daily_pct" in captured.out
    assert "pe_undervalued" in captured.out
