"""日扫描主流程：编排所有模块。

流程：
    1. 节假日检查 → 命中则退出码 0
    2. 加载 watchlist → 空 watchlist 退出码 4
    3. 同步推荐池（如果 latest stable-*.md 比上次更新）
    4. 对每只股拉数据（行情/财务/分红）→ 重跑 score_stable
    5. 加载昨日快照 + 历史 200 天快照
    6. 调 signals.check_signals 判定每只股的信号
    7. 触发了 → 生成报告 + 发邮件
    8. 写今日快照 + 清理 30 天前的旧快照
    9. 写运行日志

退出码：
    0  正常（含部分失败）
    2  全部行情失败
    3  SMTP 失败（报告已生成）
    4  watchlist 不存在或空
    5  watchlist 格式错误
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from tools.daily_monitor.holidays import is_holiday
from tools.daily_monitor.mail import (
    render_mail_html, render_mail_subject, send_mail_from_env,
)
from tools.daily_monitor.signals import (
    SEVERITY_CRITICAL, SEVERITY_OPPORTUNITY, SEVERITY_WATCH, check_signals,
)
from tools.daily_monitor.snapshot import (
    cleanup_old_snapshots, load_snapshot, write_snapshot,
)
from tools.daily_monitor.smtp_loader import DEFAULT_SMTP_ENV_PATH, SmtpConfigError
from tools.daily_monitor.watchlist import (
    DEFAULT_WATCHLIST_PATH, WatchlistError, load_watchlist, sync_recommended,
)
from tools.stock_recommender import (
    calc_dividend_yield, fetch_dividends, fetch_financials, fetch_quote,
    score_stable,
)


# 默认目录（均可在测试中 monkeypatch 替换）
DEFAULT_SNAPSHOT_DIR = DEFAULT_WATCHLIST_PATH.parent
DEFAULT_REPORT_DIR = (
    DEFAULT_WATCHLIST_PATH.parent.parent.parent / "reports" / "日扫描"
)
DEFAULT_LOG_DIR = (
    DEFAULT_WATCHLIST_PATH.parent.parent.parent / "logs" / "daily-monitor"
)
DEFAULT_STABLE_REPORT_DIR = (
    DEFAULT_WATCHLIST_PATH.parent.parent.parent / "reports" / "股票推荐"
)


@dataclass
class RunResult:
    """run() 的返回值。"""
    exit_code: int = 0
    triggered_count: int = 0
    total_scanned: int = 0
    triggered_codes: list = field(default_factory=list)
    error: str = ""


def _scan_one(code: str) -> dict:
    """拉一只股的全量数据 + 打分。失败抛异常（由上游处理）。"""
    quote = fetch_quote(code)
    fins = fetch_financials(code, years=3)
    divs = fetch_dividends(code)
    price = float(quote.get("price", 0) or 0)
    pe_raw = quote.get("pe", "-")
    pe = float(pe_raw) if pe_raw not in ("-", "", None) else None
    pb_raw = quote.get("pb", "-")
    pb = float(pb_raw) if pb_raw not in ("-", "", None) else None
    div_per_10 = divs["dividend_per_10_ttm"]
    div_yield = calc_dividend_yield(div_per_10, price)
    roe_history = fins["roe_history"]
    fund = {
        "code": code,
        "name": quote.get("name", code),
        "price": price,
        "prev_close": float(quote.get("prev_close", 0) or 0),
        "pe": pe,
        "pb": pb,
        "market_cap_yi": float(quote.get("market_cap_yi", 0) or 0),
        "dividend_yield": div_yield,
        "roe_history": roe_history,
    }
    result = score_stable(fund)
    fund["score"] = result["score"]
    return fund


def _generate_report_md(scan_date: str, market_date: str, result_summary: dict) -> str:
    """生成 Markdown 报告。"""
    lines = [
        f"# 日扫描 — {scan_date}",
        "",
        f"> 反映 {market_date}（上一交易日）市场。",
        "",
        f"- 扫描 watchlist 共 {result_summary['total_scanned']} 只",
        f"- 触发信号：{len(result_summary['triggered_codes'])} 只",
        "",
    ]
    if not result_summary["triggered_codes"]:
        lines.append("_本期无异动_")
        return "\n".join(lines)

    sev_label = {
        SEVERITY_CRITICAL: "🔴 紧急",
        SEVERITY_WATCH: "🟡 关注",
        SEVERITY_OPPORTUNITY: "🟢 机会",
    }
    for sev in (SEVERITY_CRITICAL, SEVERITY_WATCH, SEVERITY_OPPORTUNITY):
        items = [it for it in result_summary["items"] if it["top_severity"] == sev]
        if not items:
            continue
        lines.append(f"## {sev_label[sev]}（{len(items)}）")
        lines.append("")
        lines.append("| 股票 | 信号 | 数值 | 阈值 | 建议命令 |")
        lines.append("|---|---|---|---|---|")
        for it in items:
            signal_details = " / ".join(s.detail for s in it["signals"])
            actual = " / ".join(s.actual_value for s in it["signals"])
            thresh = " / ".join(s.threshold for s in it["signals"])
            cmds = []
            seen = set()
            for s in it["signals"]:
                if s.suggest_cmd not in seen:
                    cmds.append(f"`{s.suggest_cmd}`")
                    seen.add(s.suggest_cmd)
            lines.append(
                f"| {it['code']} {it['name']} | {signal_details} | {actual} | "
                f"{thresh} | {'<br>'.join(cmds)} |"
            )
        lines.append("")
    return "\n".join(lines)


def _write_log(
    *,
    scan_date: str,
    result: RunResult,
    failures: list | None = None,
    dry_run: bool = False,
    no_mail: bool = False,
    force_mail: bool = False,
) -> None:
    """写运行日志到 DEFAULT_LOG_DIR/{YYYYMMDD-HHMMSS}.json。

    所有 early return 路径都调用本函数，确保故障排查入口完整。
    failures 为 None 表示在拉数据阶段之前就退出（节假日/watchlist 错误）。
    """
    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_time = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "scan_date": scan_date,
        "exit_code": result.exit_code,
        "total_scanned": result.total_scanned,
        "triggered_count": result.triggered_count,
        "triggered_codes": result.triggered_codes,
        "failures": failures if failures is not None else [],
        "error": result.error,
        "dry_run": dry_run,
        "no_mail": no_mail,
        "force_mail": force_mail,
    }
    log_path = DEFAULT_LOG_DIR / f"{log_time}.json"
    log_path.write_text(
        json.dumps(log_entry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[log] 运行日志：{log_path}", file=sys.stderr)


def run(
    *,
    scan_date: str,
    send_email: bool = True,
    force_mail: bool = False,
    dry_run: bool = False,
    no_mail: bool = False,
) -> RunResult:
    """执行日扫描。返回 RunResult。"""
    result = RunResult()
    # 简化：扫描日即市场反映日（03:00 跑反映前一日，但快照文件按 scan_date）
    market_date = scan_date

    # 1. 节假日检查
    if is_holiday(scan_date):
        print(f"[info] {scan_date} 是节假日，跳过扫描", file=sys.stderr)
        _write_log(scan_date=scan_date, result=result)
        return result  # exit_code=0

    # 2. 加载 watchlist
    try:
        wl = load_watchlist(DEFAULT_WATCHLIST_PATH)
    except WatchlistError as e:
        print(f"❌ watchlist 格式错误: {e}", file=sys.stderr)
        result.exit_code = 5
        result.error = str(e)
        _write_log(scan_date=scan_date, result=result)
        return result

    positions = wl.get("positions", [])
    recommended = [r for r in wl.get("recommended", []) if r.get("still_recommended", True)]

    # 去重合并持仓 + 活跃推荐（持仓优先）
    all_codes = []
    seen = set()
    for p in positions:
        if p["code"] not in seen:
            all_codes.append(("position", p))
            seen.add(p["code"])
    for r in recommended:
        if r["code"] not in seen:
            all_codes.append(("recommended", r))
            seen.add(r["code"])

    if not all_codes:
        print(
            "❌ watchlist 为空（无持仓 + 无活跃推荐），先跑 add-position 或 sync-recommended",
            file=sys.stderr,
        )
        result.exit_code = 4
        _write_log(scan_date=scan_date, result=result)
        return result

    # 3. 同步推荐池（最新 stable-*.md 比上次更新则刷一次，不阻塞主流程）
    if DEFAULT_STABLE_REPORT_DIR.exists():
        candidates = sorted(
            DEFAULT_STABLE_REPORT_DIR.glob("stable-*.md"), reverse=True
        )
        if candidates:
            try:
                wl = sync_recommended(
                    DEFAULT_WATCHLIST_PATH, candidates[0], checked_date=scan_date,
                )
                # 同步后重新取活跃推荐（避免引入新代码遗漏扫描）
                recommended = [
                    r for r in wl.get("recommended", [])
                    if r.get("still_recommended", True)
                ]
                # 把新进的活跃推荐补进 all_codes
                for r in recommended:
                    if r["code"] not in seen:
                        all_codes.append(("recommended", r))
                        seen.add(r["code"])
            except Exception as e:
                print(f"[warn] sync-recommended 失败（不阻塞）: {e}", file=sys.stderr)

    thresholds = wl["thresholds"]

    # 4. 加载昨日快照 + 历史快照（用于 52 周新高低）
    today = date.fromisoformat(scan_date)
    prev_snap_path = None
    for i in range(1, 15):  # 最多回溯 2 周找上一个工作日的快照
        prev_date = today - timedelta(days=i)
        prev_path = DEFAULT_SNAPSHOT_DIR / f"snapshot-{prev_date.isoformat()}.json"
        if prev_path.exists():
            prev_snap_path = prev_path
            break
    yesterday_snap = (
        load_snapshot(prev_snap_path).get("stocks", {}) if prev_snap_path else None
    )

    historical_snaps = []
    if DEFAULT_SNAPSHOT_DIR.exists():
        for entry in sorted(DEFAULT_SNAPSHOT_DIR.glob("snapshot-*.json")):
            try:
                historical_snaps.append(json.loads(entry.read_text(encoding="utf-8")))
            except Exception:
                continue

    # 5. 拉数据 + 打分
    today_stocks = {}
    failures = []
    for kind, item in all_codes:
        code = item["code"]
        try:
            data = _scan_one(code)
            today_stocks[code] = data
            print(
                f"  [{code}] {data['name']}: score={data['score']}, "
                f"price={data['price']}, pe={data['pe']}",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"  [{code}] ⚠️ 拉数据失败: {e}", file=sys.stderr)
            failures.append(code)

    if not today_stocks and all_codes:
        print(
            f"❌ 全部行情失败（{len(failures)} 只），不发邮件", file=sys.stderr
        )
        result.exit_code = 2
        result.error = f"all {len(failures)} stocks failed"
        _write_log(
            scan_date=scan_date, result=result, failures=failures,
            dry_run=dry_run, no_mail=no_mail, force_mail=force_mail,
        )
        return result

    # 6. 信号判定
    signals_by_code = {}
    triggered_codes = []
    items = []
    position_codes = {p["code"] for p in positions}
    recommended_history_codes = {
        r["code"] for r in wl.get("recommended", [])
        if not r.get("still_recommended", True)
    }

    for kind, item in all_codes:
        code = item["code"]
        if code not in today_stocks:
            continue
        today_data = today_stocks[code]
        # 注入 buy_price（持仓专属）
        if kind == "position":
            today_data["buy_price"] = item.get("buy_price")

        yesterday_stock = (yesterday_snap or {}).get(code)
        last_5d_close = None  # 5 日累计信号暂不实现（plan 留 TODO）

        sigs = check_signals(
            today=today_data,
            yesterday=yesterday_stock,
            last_5d_close=last_5d_close,
            thresholds=thresholds,
            is_position=(code in position_codes),
            snapshots_for_52w=historical_snaps,
            was_recommended_before=(code in recommended_history_codes),
        )
        if sigs:
            signals_by_code[code] = sigs
            triggered_codes.append(code)
            sev_rank = {
                SEVERITY_CRITICAL: 0, SEVERITY_WATCH: 1, SEVERITY_OPPORTUNITY: 2,
            }
            top_sev = min((s.severity for s in sigs), key=lambda x: sev_rank.get(x, 99))
            items.append({
                "code": code, "name": today_data["name"],
                "signals": sigs, "top_severity": top_sev,
            })

    result.triggered_count = len(triggered_codes)
    result.total_scanned = len(today_stocks)
    result.triggered_codes = triggered_codes

    # 7. 写今日快照 + 清理旧快照
    if not dry_run:
        snap = {"scan_date": scan_date, "stocks": today_stocks}
        write_snapshot(snap, DEFAULT_SNAPSHOT_DIR / f"snapshot-{scan_date}.json")
        cleanup_old_snapshots(
            DEFAULT_SNAPSHOT_DIR,
            keep_days=thresholds.get("snapshot_history_days", 30),
            today_str=scan_date,
        )

    # 8. 触发了 → 生成报告 + 发邮件
    should_mail = (
        (result.triggered_count > 0 or force_mail)
        and send_email and not no_mail
    )
    if result.triggered_count > 0 or dry_run:
        summary = {
            "total_scanned": result.total_scanned,
            "triggered_codes": triggered_codes,
            "items": items,
        }
        report_md = _generate_report_md(scan_date, market_date, summary)
        if not dry_run:
            DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            (DEFAULT_REPORT_DIR / f"{scan_date}.md").write_text(
                report_md, encoding="utf-8"
            )

    if should_mail:
        try:
            untriggered = [
                c for c, _ in all_codes
                if c not in triggered_codes and c in today_stocks
            ]
            subject = render_mail_subject(
                scan_date=scan_date, triggered_count=result.triggered_count,
            )
            html = render_mail_html(
                scan_date=scan_date, market_date=market_date,
                total_scanned=result.total_scanned,
                triggered_count=result.triggered_count,
                signals_by_code=signals_by_code,
                untriggered_codes=untriggered,
            )
            send_mail_from_env(
                subject=subject, html_body=html, env_path=DEFAULT_SMTP_ENV_PATH,
            )
            print(f"✅ 邮件已发送：{subject}", file=sys.stderr)
        except SmtpConfigError as e:
            print(f"⚠️ SMTP 配置错误（报告已生成）: {e}", file=sys.stderr)
            result.exit_code = 3
        except Exception as e:
            print(f"⚠️ 邮件发送失败（报告已生成）: {e}", file=sys.stderr)
            result.exit_code = 3

    print(
        f"[done] 扫描 {result.total_scanned} 只，触发 {result.triggered_count} 只",
        file=sys.stderr,
    )
    _write_log(
        scan_date=scan_date, result=result, failures=failures,
        dry_run=dry_run, no_mail=no_mail, force_mail=force_mail,
    )
    return result
