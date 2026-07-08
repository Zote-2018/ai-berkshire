"""daily_monitor CLI 入口。

子命令：
    add-position CODE --buy-price N --shares N --buy-date YYYY-MM-DD
    remove-position CODE
    sync-recommended
    show-watchlist
    show-snapshot --date YYYY-MM-DD
    show-config
    run [--dry-run] [--no-mail] [--force-mail]
"""

import argparse
import sys


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
    p_add.add_argument("--name", default="", help="股票名称（可选，自动抓取失败时用）")

    p_rm = sub.add_parser("remove-position", help="删除持仓")
    p_rm.add_argument("code", help="股票代码")

    sub.add_parser("sync-recommended", help="从最新 stable-{date}.md 同步推荐池")

    sub.add_parser("show-watchlist", help="打印当前 watchlist")
    p_snap = sub.add_parser("show-snapshot", help="打印某日快照")
    p_snap.add_argument("--date", required=True, help="YYYY-MM-DD")

    sub.add_parser("show-config", help="打印阈值配置")

    p_run = sub.add_parser("run", help="执行日扫描")
    p_run.add_argument("--dry-run", action="store_true", help="只打印，不写文件不发邮件")
    p_run.add_argument("--no-mail", action="store_true", help="跑但不发邮件")
    p_run.add_argument("--force-mail", action="store_true", help="即使无异动也发邮件（测试用）")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    print(f"[stub] 收到子命令: {args.cmd}", file=sys.stderr)
    print(f"[stub] 参数: {vars(args)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
