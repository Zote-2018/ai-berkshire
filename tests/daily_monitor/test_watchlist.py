"""tools.daily_monitor.watchlist 单元测试。"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


from tools.daily_monitor.watchlist import (
    DEFAULT_THRESHOLDS,
    WatchlistError,
    add_position,
    load_watchlist,
    remove_position,
    save_watchlist,
)


# ---------------------------------------------------------------------------
# load_watchlist
# ---------------------------------------------------------------------------

def test_load_文件不存在_返回默认结构(tmp_watchlist_path):
    """文件不存在时返回空 watchlist（含默认 thresholds）。"""
    wl = load_watchlist(tmp_watchlist_path)
    assert wl["version"] == 1
    assert wl["positions"] == []
    assert wl["recommended"] == []
    assert wl["thresholds"] == DEFAULT_THRESHOLDS


def test_load_完整文件_往返一致(sample_watchlist_file, sample_watchlist_data):
    """加载已有文件，数据完整。"""
    wl = load_watchlist(sample_watchlist_file)
    assert wl == sample_watchlist_data


def test_load_格式错误_抛异常(tmp_watchlist_path):
    """JSON 格式错误时抛 WatchlistError，含文件路径信息。"""
    tmp_watchlist_path.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(WatchlistError) as exc:
        load_watchlist(tmp_watchlist_path)
    assert "watchlist.json" in str(exc.value) or "JSON" in str(exc.value)


def test_load_缺thresholds_补默认(tmp_watchlist_path):
    """老格式（无 thresholds 字段）自动补默认。"""
    tmp_watchlist_path.write_text(
        '{"version": 1, "positions": [], "recommended": []}',
        encoding="utf-8",
    )
    wl = load_watchlist(tmp_watchlist_path)
    assert wl["thresholds"] == DEFAULT_THRESHOLDS


# ---------------------------------------------------------------------------
# save_watchlist
# ---------------------------------------------------------------------------

def test_save_往返不丢字段(tmp_watchlist_path, sample_watchlist_data):
    """save → load 往返，字段一致。"""
    save_watchlist(sample_watchlist_data, tmp_watchlist_path)
    reloaded = load_watchlist(tmp_watchlist_path)
    assert reloaded == sample_watchlist_data


def test_save_中文不转义(sample_watchlist_file):
    """保存时 ensure_ascii=False，中文不被转成 \\uXXXX。"""
    content = sample_watchlist_file.read_text(encoding="utf-8")
    assert "贵州茅台" in content
    assert "\\u" not in content


# ---------------------------------------------------------------------------
# add_position
# ---------------------------------------------------------------------------

def test_add_position_首次添加(tmp_watchlist_path):
    """空 watchlist 添加第一只持仓。"""
    wl = add_position(
        tmp_watchlist_path,
        code="600036",
        name="招商银行",
        buy_price=38.5,
        shares=1000,
        buy_date="2026-03-15",
    )
    assert len(wl["positions"]) == 1
    pos = wl["positions"][0]
    assert pos["code"] == "600036"
    assert pos["name"] == "招商银行"
    assert pos["buy_price"] == 38.5
    assert pos["shares"] == 1000
    assert pos["buy_date"] == "2026-03-15"
    assert "added_at" in pos


def test_add_position_重复码_抛异常(sample_watchlist_file):
    """已存在的 code 不能重复添加。"""
    with pytest.raises(WatchlistError) as exc:
        add_position(
            sample_watchlist_file,
            code="600519",
            name="贵州茅台",
            buy_price=1700,
            shares=200,
            buy_date="2026-04-01",
        )
    assert "已存在" in str(exc.value) or "600519" in str(exc.value)


def test_add_position_多次添加不同股(tmp_watchlist_path):
    """连续添加 3 只不同股票，顺序保留。"""
    for code, name in [("600036", "招商银行"), ("000858", "五粮液"), ("601318", "中国平安")]:
        add_position(
            tmp_watchlist_path,
            code=code, name=name, buy_price=100, shares=100, buy_date="2026-03-15",
        )
    wl = load_watchlist(tmp_watchlist_path)
    assert [p["code"] for p in wl["positions"]] == ["600036", "000858", "601318"]


# ---------------------------------------------------------------------------
# remove_position
# ---------------------------------------------------------------------------

def test_remove_position_正常删除(sample_watchlist_file):
    """存在的 code 删除后 watchlist.positions 为空。"""
    wl = remove_position(sample_watchlist_file, code="600519")
    assert wl["positions"] == []
    # recommended 不受影响
    assert len(wl["recommended"]) == 1


def test_remove_position_不存在_抛异常(sample_watchlist_file):
    """不存在的 code 抛异常。"""
    with pytest.raises(WatchlistError):
        remove_position(sample_watchlist_file, code="999999")
