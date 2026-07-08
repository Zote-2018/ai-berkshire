"""daily_monitor CLI 入口。

子命令：
    add-position CODE --buy-price N --shares N --buy-date YYYY-MM-DD [--name NAME]
    remove-position CODE
    sync-recommended
    show-watchlist
    show-snapshot --date YYYY-MM-DD
    show-config
    run [--dry-run] [--no-mail] [--force-mail]
"""

import argparse
import json
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily_monitor",
        description="A 股日扫描：watchlist 日频监控 + 半自动邮件提醒",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add-position", help="添加持仓")
    p_add.add_argument("code", help="股票代码（如 600036）")
    p_add.add_argument("--buy-price", type=float, required=True, help="买入价")
    p_add.add_argument("--shares", type=int, required=True, help="持仓股数")
    p_add.add_argument("--buy-date", required=True, help="买入日期 YYYY-MM-DD")
    p_add.add_argument("--name", default="", help="股票名称（可选）")

    p_rm = sub.add_parser("remove-position", help="删除持仓")
    p_rm.add_argument("code", help="股票代码")

    sub.add_parser("sync-recommended", help="从最新 stable-{date}.md 同步推荐池")

    sub.add_parser("show-watchlist", help="打印当前 watchlist")
    p_snap = sub.add_parser("show-snapshot", help="打印某日快照")
    p_snap.add_argument("--date", required=True, help="YYYY-MM-DD")

    sub.add_parser("show-config", help="打印阈值配置")

    p_run = sub.add_parser("run", help="执行日扫描")
    p_run.add_argument("--dry-run", action="store_true", help="只打印，不写不发")
    p_run.add_argument("--no-mail", action="store_true", help="跑但不发邮件")
    p_run.add_argument("--force-mail", action="store_true", help="即使无异动也发")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # 延迟 import，避免 CLI 解析时把所有模块都加载
    from tools.daily_monitor.watchlist import (
        DEFAULT_WATCHLIST_PATH, WatchlistError,
        add_position, remove_position, load_watchlist,
    )

    if args.cmd == "add-position":
        try:
            add_position(
                DEFAULT_WATCHLIST_PATH,
                code=args.code,
                name=args.name or args.code,
                buy_price=args.buy_price,
                shares=args.shares,
                buy_date=args.buy_date,
            )
        except WatchlistError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1
        print(f"✅ 已添加 {args.code}", file=sys.stderr)
        return 0

    if args.cmd == "remove-position":
        try:
            remove_position(DEFAULT_WATCHLIST_PATH, code=args.code)
        except WatchlistError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1
        print(f"✅ 已删除 {args.code}", file=sys.stderr)
        return 0

    if args.cmd == "show-watchlist":
        wl = load_watchlist(DEFAULT_WATCHLIST_PATH)
        print(json.dumps(wl, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "show-config":
        wl = load_watchlist(DEFAULT_WATCHLIST_PATH)
        print(json.dumps(wl["thresholds"], ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "sync-recommended":
        from datetime import date
        # 找最新的 stable-{date}.md（按文件名降序排，最新的在前）
        reports_dir = Path(__file__).resolve().parent.parent.parent / "reports" / "股票推荐"
        if not reports_dir.exists():
            print(f"❌ 报告目录不存在: {reports_dir}", file=sys.stderr)
            return 1
        candidates = sorted(reports_dir.glob("stable-*.md"), reverse=True)
        if not candidates:
            print(f"❌ {reports_dir} 下无 stable-*.md 报告", file=sys.stderr)
            return 1
        latest = candidates[0]
        from tools.daily_monitor.watchlist import sync_recommended
        try:
            wl = sync_recommended(
                DEFAULT_WATCHLIST_PATH, latest,
                checked_date=date.today().isoformat(),
            )
        except Exception as e:
            print(f"❌ 同步失败: {e}", file=sys.stderr)
            return 1
        active = [r for r in wl["recommended"] if r["still_recommended"]]
        print(
            f"✅ 同步完成：{len(active)} 只活跃推荐"
            f"（共 {len(wl['recommended'])} 条记录）",
            file=sys.stderr,
        )
        print(f"   报告：{latest.name}", file=sys.stderr)
        return 0

    if args.cmd == "show-snapshot":
        print(f"[stub] show-snapshot 尚未实现（Task 5），date={args.date}", file=sys.stderr)
        return 0

    if args.cmd == "run":
        print("[stub] run 尚未实现（Task 9）", file=sys.stderr)
        return 0

    parser.error(f"未知子命令: {args.cmd}")  # 必抛 SystemExit(2)


if __name__ == "__main__":
    sys.exit(main())
