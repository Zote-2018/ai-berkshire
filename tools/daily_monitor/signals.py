"""4 类信号判定 + 严重度分级。

输入：
    today: 今日数据 {code, name, price, prev_close, pe, pb, dividend_yield, score, buy_price?}
    yesterday: 昨日快照的 stocks[code] dict 或 None（首次运行）
    last_5d_close: 5 个交易日前的收盘价（None 时不触发 5 日信号）
    thresholds: 阈值字典（来自 watchlist.json）
    is_position: True=持仓 / False=推荐池
    snapshots_for_52w: 历史 200+ 个快照列表（用于 52 周新高低）
    was_recommended_before: 历史推荐过但当前跌出（用于"重新进入"信号）

输出：Signal 列表（一只股可触发多个）。

严重度：CRITICAL（紧急）/ WATCH（关注）/ OPPORTUNITY（机会）
"""

from dataclasses import dataclass
from typing import Optional


SEVERITY_CRITICAL = "critical"
SEVERITY_WATCH = "watch"
SEVERITY_OPPORTUNITY = "opportunity"


@dataclass
class Signal:
    """单条触发信号。"""
    code: str
    name: str
    type: str                 # 如 "price_daily_up" / "pe_undervalued"
    severity: str             # SEVERITY_*
    detail: str               # 人话描述，如 "单日跌 5.2%"
    actual_value: str         # 实际值，如 "5.2%"
    threshold: str            # 触发阈值，如 "±5%"
    suggest_cmd: str          # 建议命令，如 "/news-pulse 招商银行 跌5% 1天"


# 52 周新高低需要的最小快照数（约 9 个月交易日）
_MIN_SNAPSHOTS_52W = 200


def _pct_change(new: float, old: float) -> float:
    """(new - old) / old * 100。old=0 时返回 0。"""
    if old == 0:
        return 0.0
    return (new - old) / old * 100.0


def check_signals(
    *,
    today: dict,
    yesterday: Optional[dict],
    last_5d_close: Optional[float],
    thresholds: dict,
    is_position: bool,
    snapshots_for_52w: list,
    was_recommended_before: bool = False,
) -> list:
    """判定一只股今日触发的所有信号。返回 Signal 列表（可能为空）。"""
    signals = []
    code = today["code"]
    name = today.get("name", code)
    price = today.get("price", 0) or 0
    prev_close = today.get("prev_close", 0) or 0

    # === 1. 价格异动 ===
    if prev_close > 0:
        daily_pct = _pct_change(price, prev_close)
        threshold_daily = thresholds["price_change_daily_pct"]
        if daily_pct >= threshold_daily:
            signals.append(Signal(
                code=code, name=name, type="price_daily_up", severity=SEVERITY_WATCH,
                detail=f"单日涨 {daily_pct:.1f}%",
                actual_value=f"+{daily_pct:.1f}%",
                threshold=f"+{threshold_daily:.1f}%",
                suggest_cmd=f"/news-pulse {name} 涨{daily_pct:.0f}% 1天",
            ))
        elif daily_pct <= -threshold_daily:
            signals.append(Signal(
                code=code, name=name, type="price_daily_down", severity=SEVERITY_WATCH,
                detail=f"单日跌 {abs(daily_pct):.1f}%",
                actual_value=f"{daily_pct:.1f}%",
                threshold=f"-{threshold_daily:.1f}%",
                # 修正 bug：单日跌是 1 天，不是 5 天（plan 模板误写）
                suggest_cmd=f"/news-pulse {name} 跌{abs(daily_pct):.0f}% 1天",
            ))

    # 5 日累计
    if last_5d_close and last_5d_close > 0:
        pct_5d = _pct_change(price, last_5d_close)
        threshold_5d = thresholds["price_change_5d_pct"]
        if pct_5d >= threshold_5d:
            signals.append(Signal(
                code=code, name=name, type="price_5d_up", severity=SEVERITY_WATCH,
                detail=f"5 日累计涨 {pct_5d:.1f}%",
                actual_value=f"+{pct_5d:.1f}%",
                threshold=f"+{threshold_5d:.1f}%",
                suggest_cmd=f"/news-pulse {name} 涨{pct_5d:.0f}% 5天",
            ))
        elif pct_5d <= -threshold_5d:
            signals.append(Signal(
                code=code, name=name, type="price_5d_down", severity=SEVERITY_WATCH,
                detail=f"5 日累计跌 {abs(pct_5d):.1f}%",
                actual_value=f"{pct_5d:.1f}%",
                threshold=f"-{threshold_5d:.1f}%",
                suggest_cmd=f"/news-pulse {name} 跌{abs(pct_5d):.0f}% 5天",
            ))

    # 跌破成本（仅持仓）
    if is_position and today.get("buy_price"):
        buy_price = today["buy_price"]
        drawdown_pct = _pct_change(price, buy_price)
        threshold_dd = thresholds["cost_drawdown_pct"]
        if drawdown_pct <= -threshold_dd:
            signals.append(Signal(
                code=code, name=name, type="cost_drawdown", severity=SEVERITY_CRITICAL,
                detail=f"跌破成本 {abs(drawdown_pct):.1f}%",
                actual_value=f"{drawdown_pct:.1f}%",
                threshold=f"-{threshold_dd:.1f}%",
                suggest_cmd=f"/thesis-tracker {name}",
            ))

    # 52 周新高低（需 ≥ 200 个快照）
    if len(snapshots_for_52w) >= _MIN_SNAPSHOTS_52W:
        historical_prices = []
        for snap in snapshots_for_52w:
            stock = snap.get("stocks", {}).get(code)
            if stock and stock.get("price"):
                historical_prices.append(stock["price"])
        if historical_prices:
            lowest = min(historical_prices)
            highest = max(historical_prices)
            if price < lowest:
                signals.append(Signal(
                    code=code, name=name, type="new_52w_low", severity=SEVERITY_CRITICAL,
                    detail=f"创 52 周新低（{price} < {lowest}）",
                    actual_value=f"{price}",
                    threshold=f"历史最低 {lowest}",
                    suggest_cmd=f"/thesis-tracker {name}",
                ))
            elif price > highest:
                signals.append(Signal(
                    code=code, name=name, type="new_52w_high", severity=SEVERITY_OPPORTUNITY,
                    detail=f"创 52 周新高（{price} > {highest}）",
                    actual_value=f"{price}",
                    threshold=f"历史最高 {highest}",
                    suggest_cmd=f"/thesis-tracker {name}",
                ))

    # === 2. 估值变化 ===
    pe = today.get("pe")
    if pe is not None and pe > 0:
        if pe < thresholds["pe_undervalued"]:
            signals.append(Signal(
                code=code, name=name, type="pe_undervalued", severity=SEVERITY_OPPORTUNITY,
                detail=f"PE 进入击球区（{pe}）",
                actual_value=f"{pe}",
                threshold=f"< {thresholds['pe_undervalued']}",
                suggest_cmd=f"/investment-checklist {name}",
            ))
        elif pe > thresholds["pe_overvalued"]:
            signals.append(Signal(
                code=code, name=name, type="pe_overvalued", severity=SEVERITY_CRITICAL,
                detail=f"PE 突破高估区（{pe}）",
                actual_value=f"{pe}",
                threshold=f"> {thresholds['pe_overvalued']}",
                suggest_cmd=f"/thesis-tracker {name}",
            ))

    div_y = today.get("dividend_yield")
    if div_y is not None:
        if div_y >= thresholds["dividend_yield_high"]:
            signals.append(Signal(
                code=code, name=name, type="dividend_yield_high", severity=SEVERITY_OPPORTUNITY,
                detail=f"股息率升破临界（{div_y:.2f}%）",
                actual_value=f"{div_y:.2f}%",
                threshold=f">= {thresholds['dividend_yield_high']}%",
                suggest_cmd=f"/investment-checklist {name}",
            ))
        elif div_y < thresholds["dividend_yield_low"]:
            signals.append(Signal(
                code=code, name=name, type="dividend_yield_low", severity=SEVERITY_CRITICAL,
                detail=f"股息率跌破临界（{div_y:.2f}%）",
                actual_value=f"{div_y:.2f}%",
                threshold=f"< {thresholds['dividend_yield_low']}%",
                suggest_cmd=f"/thesis-tracker {name}",
            ))

    pb = today.get("pb")
    if pb is not None and pb < 1.0:
        signals.append(Signal(
            code=code, name=name, type="pb_below_1", severity=SEVERITY_OPPORTUNITY,
            detail=f"PB 破净（{pb}）",
            actual_value=f"{pb}",
            threshold="< 1.0",
            suggest_cmd=f"/investment-checklist {name}",
        ))

    # === 3. 推荐池变动 ===
    # 注意 yesterday 的两种形式：
    #   1. {code: {score: ...}} 完整昨日快照 stocks dict（来自 snapshot.py）→ 从 yesterday[code] 取
    #   2. {score: ...} 单股数据 dict → 直接从 yesterday 取
    today_score = today.get("score")
    yesterday_data: Optional[dict] = None
    if yesterday:
        if code in yesterday:
            yesterday_data = yesterday[code]
        else:
            yesterday_data = yesterday
    yesterday_score = yesterday_data.get("score") if yesterday_data else None

    if today_score == 4:
        if yesterday_score is None or yesterday_score < 4:
            if was_recommended_before:
                # 历史推荐过、跌出、现在重新进入
                signals.append(Signal(
                    code=code, name=name, type="recommended_reenter", severity=SEVERITY_OPPORTUNITY,
                    detail="重新进入 4 分强推荐",
                    actual_value="4 分",
                    threshold="4 分强推荐",
                    suggest_cmd=f"/investment-checklist {name}",
                ))
            elif yesterday_score is None:
                # 首次进入
                signals.append(Signal(
                    code=code, name=name, type="recommended_new", severity=SEVERITY_OPPORTUNITY,
                    detail="新进 4 分强推荐",
                    actual_value="4 分",
                    threshold="4 分强推荐",
                    suggest_cmd=f"/investment-checklist {name}",
                ))
    elif today_score is not None and today_score < 4 and yesterday_score == 4:
        signals.append(Signal(
            code=code, name=name, type="recommended_drop", severity=SEVERITY_CRITICAL,
            detail=f"从 4 分跌出（今日 {today_score} 分）",
            actual_value=f"{today_score} 分",
            threshold="< 4 分",
            suggest_cmd=f"/thesis-tracker {name}",
        ))

    return signals
