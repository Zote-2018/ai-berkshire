"""tools.daily_monitor.signals 单元测试。

信号判定是日扫描的核心：4 类信号 + 严重度分级。
边界值测试密集。
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from tools.daily_monitor.signals import (
    SEVERITY_CRITICAL,
    SEVERITY_WATCH,
    SEVERITY_OPPORTUNITY,
    Signal,
    check_signals,
)


def _today_data(
    *, code="600036", name="招商银行", price=10.0, prev_close=10.0,
    pe=15.0, pb=2.0, dividend_yield=4.0, score=4,
    buy_price=None,
):
    """构造今日单股数据。"""
    return {
        "code": code, "name": name, "price": price, "prev_close": prev_close,
        "pe": pe, "pb": pb, "dividend_yield": dividend_yield, "score": score,
        "buy_price": buy_price,
    }


def _thresholds(**overrides):
    """构造阈值，默认 + 自定义覆盖。"""
    base = {
        "price_change_daily_pct": 5.0,
        "price_change_5d_pct": 10.0,
        "cost_drawdown_pct": 15.0,
        "pe_undervalued": 8,
        "pe_overvalued": 20,
        "dividend_yield_high": 5.0,
        "dividend_yield_low": 3.0,
        "snapshot_history_days": 30,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 价格异动
# ---------------------------------------------------------------------------

def test_价格_单日涨超5pct触发():
    today = _today_data(price=10.5, prev_close=10.0)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    types = [s.type for s in signals]
    assert "price_daily_up" in types
    assert signals[0].severity == SEVERITY_WATCH


def test_价格_单日涨刚好5pct触发_边界值():
    """5.0% 应触发（>=阈值）。"""
    today = _today_data(price=10.5, prev_close=10.0)
    # price=10.5, prev=10.0 → +5.0%，等于阈值，应触发
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "price_daily_up" for s in signals)


def test_价格_单日涨4_9pct不触发():
    today = _today_data(price=10.49, prev_close=10.0)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert not any(s.type == "price_daily_up" for s in signals)


def test_价格_单日跌5pct触发():
    today = _today_data(price=9.5, prev_close=10.0)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "price_daily_down" for s in signals)


def test_价格_5日累计涨10pct触发():
    today = _today_data(price=11.0)
    # last_5d_close 是 5 个交易日前的收盘
    signals = check_signals(today=today, yesterday=None, last_5d_close=10.0,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "price_5d_up" for s in signals)


def test_价格_跌破成本15pct触发_紧急():
    today = _today_data(price=8.5, buy_price=10.0)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    critical = [s for s in signals if s.type == "cost_drawdown"]
    assert len(critical) == 1
    assert critical[0].severity == SEVERITY_CRITICAL


def test_价格_跌破成本刚好15pct触发():
    today = _today_data(price=8.5, buy_price=10.0)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "cost_drawdown" for s in signals)


def test_价格_推荐池股票不算成本止损():
    """非持仓（推荐池）不触发 cost_drawdown。"""
    today = _today_data(price=8.5, buy_price=None)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=False,
                            snapshots_for_52w=[])
    assert not any(s.type == "cost_drawdown" for s in signals)


def test_价格_52周新低_紧急():
    """快照积累 ≥ 200 天时，今日收盘低于所有历史最低 → 触发。"""
    today = _today_data(price=8.0)
    # 模拟 200 个快照，最低价 9.0
    snapshots = [{"stocks": {"600036": {"price": 9.0 + i * 0.01}}} for i in range(200)]
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=snapshots)
    assert any(s.type == "new_52w_low" for s in signals)


def test_价格_52周新低_快照不足不触发():
    """快照 < 200 个时不触发（数据不够）。"""
    today = _today_data(price=8.0)
    snapshots = [{"stocks": {"600036": {"price": 9.0}}} for _ in range(199)]
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=snapshots)
    assert not any(s.type == "new_52w_low" for s in signals)


# ---------------------------------------------------------------------------
# 估值变化
# ---------------------------------------------------------------------------

def test_估值_PE进入击球区_机会():
    today = _today_data(pe=7.5)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    opp = [s for s in signals if s.type == "pe_undervalued"]
    assert len(opp) == 1
    assert opp[0].severity == SEVERITY_OPPORTUNITY


def test_估值_PE突破高估_紧急():
    today = _today_data(pe=22)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "pe_overvalued" and s.severity == SEVERITY_CRITICAL for s in signals)


def test_估值_股息率升破5pct_机会():
    today = _today_data(dividend_yield=5.5)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "dividend_yield_high" for s in signals)


def test_估值_股息率跌破3pct_紧急():
    today = _today_data(dividend_yield=2.5)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "dividend_yield_low" and s.severity == SEVERITY_CRITICAL for s in signals)


def test_估值_PB破净_机会():
    today = _today_data(pb=0.95)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "pb_below_1" for s in signals)


# ---------------------------------------------------------------------------
# 推荐池变动（依赖 yesterday）
# ---------------------------------------------------------------------------

def test_推荐池_新进4分强推荐_机会():
    """昨天不存在或非 4 分，今天 4 分 → 新进信号。"""
    today = _today_data(score=4)
    yesterday = None  # 首次出现
    signals = check_signals(today=today, yesterday=yesterday, last_5d_close=None,
                            thresholds=_thresholds(), is_position=False,
                            snapshots_for_52w=[])
    assert any(s.type == "recommended_new" for s in signals)


def test_推荐池_从4分跌出_紧急():
    """昨天 4 分，今天 < 4 分 → 跌出信号。"""
    today = _today_data(score=3)
    yesterday = {"600036": {"score": 4}}
    signals = check_signals(today=today, yesterday=yesterday, last_5d_close=None,
                            thresholds=_thresholds(), is_position=False,
                            snapshots_for_52w=[])
    assert any(s.type == "recommended_drop" and s.severity == SEVERITY_CRITICAL for s in signals)


def test_推荐池_重新进入_机会():
    """历史标 still_recommended=False，今天重新 4 分 → 重新进入信号。

    该信号需要 watchlist 上下文（is_recommended_history=True 表示曾推荐过）。
    """
    today = _today_data(score=4)
    yesterday = {"600036": {"score": 3}}
    signals = check_signals(today=today, yesterday=yesterday, last_5d_close=None,
                            thresholds=_thresholds(), is_position=False,
                            snapshots_for_52w=[],
                            was_recommended_before=True)
    types = [s.type for s in signals]
    assert "recommended_reenter" in types


# ---------------------------------------------------------------------------
# 多信号合并
# ---------------------------------------------------------------------------

def test_多信号_一只股触发多个():
    """同一只股同时满足多个条件，返回多个 Signal。"""
    today = _today_data(price=8.5, prev_close=10.0, pe=7.0, pb=0.9,
                        dividend_yield=6.0, buy_price=10.0)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    types = {s.type for s in signals}
    # 至少触发：单日跌、PE 击球、PB 破净、股息率升、成本止损
    assert "price_daily_down" in types
    assert "pe_undervalued" in types
    assert "pb_below_1" in types
    assert "dividend_yield_high" in types
    assert "cost_drawdown" in types
