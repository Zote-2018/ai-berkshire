"""watchlist.json 加载/保存/CRUD。

watchlist 是日扫描的核心配置：持仓 + 推荐池 + 阈值。
- positions: 手动维护（add-position / remove-position 子命令）
- recommended: 自动同步（sync-recommended 子命令，每次 run 也会刷）
- thresholds: 手动编辑（DEFAULT_THRESHOLDS 提供初值）
"""

import json
import os
import re
from datetime import date
from pathlib import Path


class WatchlistError(Exception):
    """watchlist 操作错误（文件格式错误、重复添加等）。"""


DEFAULT_WATCHLIST_PATH = Path(
    os.environ.get(
        "DAILY_MONITOR_WATCHLIST",
        str(Path(__file__).resolve().parent.parent.parent / "data" / "monitor" / "watchlist.json"),
    )
)


DEFAULT_THRESHOLDS = {
    "price_change_daily_pct": 5.0,
    "price_change_5d_pct": 10.0,
    "cost_drawdown_pct": 15.0,
    "pe_undervalued": 8,
    "pe_overvalued": 20,
    "dividend_yield_high": 5.0,
    "dividend_yield_low": 3.0,
    "snapshot_history_days": 30,
}


def _empty_watchlist() -> dict:
    return {
        "version": 1,
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "positions": [],
        "recommended": [],
    }


def load_watchlist(path: Path) -> dict:
    """加载 watchlist.json。文件不存在返回空结构；格式错误抛 WatchlistError。"""
    if not path.exists():
        return _empty_watchlist()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise WatchlistError(f"watchlist.json 格式错误 ({path}): {e}")
    if not isinstance(data, dict):
        raise WatchlistError(f"watchlist.json 顶层必须是对象 ({path})")
    # 兼容老格式：缺字段补默认
    data.setdefault("version", 1)
    data.setdefault("thresholds", dict(DEFAULT_THRESHOLDS))
    data.setdefault("positions", [])
    data.setdefault("recommended", [])
    return data


def save_watchlist(data: dict, path: Path) -> None:
    """保存 watchlist.json（UTF-8，中文不转义，缩进 2）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_position(
    path: Path,
    *,
    code: str,
    name: str,
    buy_price: float,
    shares: int,
    buy_date: str,
) -> dict:
    """添加持仓并保存。code 已存在时抛 WatchlistError。返回更新后的 watchlist。"""
    wl = load_watchlist(path)
    if any(p["code"] == code for p in wl["positions"]):
        raise WatchlistError(f"持仓已存在: {code}（先用 remove-position 删除）")
    wl["positions"].append({
        "code": code,
        "name": name,
        "buy_price": buy_price,
        "shares": shares,
        "buy_date": buy_date,
        "added_at": date.today().isoformat(),
    })
    save_watchlist(wl, path)
    return wl


def remove_position(path: Path, *, code: str) -> dict:
    """删除持仓并保存。code 不存在时抛 WatchlistError。"""
    wl = load_watchlist(path)
    before = len(wl["positions"])
    wl["positions"] = [p for p in wl["positions"] if p["code"] != code]
    if len(wl["positions"]) == before:
        raise WatchlistError(f"持仓不存在: {code}")
    save_watchlist(wl, path)
    return wl


_SECTION_STRONG = "## Top 推荐（4 分）"


def _parse_strong_section(report_text: str) -> list:
    """解析 '## Top 推荐（4 分）' 节下的表格行。

    返回 [(code, name), ...]，按报告顺序。跳过表头与分隔符行。
    节边界：从 _SECTION_STRONG 到下一个 '\n## ' 或文末。
    """
    start = report_text.find(_SECTION_STRONG)
    if start < 0:
        return []
    end = report_text.find("\n## ", start + len(_SECTION_STRONG))
    section = report_text[start: end if end > 0 else None]
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        first = cells[0]
        # 跳过分隔符行（--- 或 - - - 等）和表头
        if first == "代码" or set(first) <= {"-"}:
            continue
        if re.match(r"^\d{6}$", first):
            rows.append((first, cells[1]))
    return rows


def sync_recommended(path: Path, report_path: Path, *, checked_date: str) -> dict:
    """根据最新 stable-{date}.md 同步 watchlist.recommended。

    规则：
    - 报告里的 4 分强推荐 → still_recommended=True；新进的追加 first_recommended_date=checked_date
    - 不在报告里的旧推荐 → still_recommended=False（保留，不删除）
    - first_recommended_date 永不更新（保留首次推荐日期）
    - last_checked_date 全部更新为 checked_date
    - 按首次推荐日期升序排序（旧的在前）

    report_path 不存在时抛 FileNotFoundError。
    """
    if not report_path.exists():
        raise FileNotFoundError(f"推荐报告不存在: {report_path}")

    report_text = report_path.read_text(encoding="utf-8")
    strong_rows = _parse_strong_section(report_text)
    strong_codes = {code for code, _ in strong_rows}
    name_map = {code: name for code, name in strong_rows}

    wl = load_watchlist(path)
    existing = {r["code"]: r for r in wl["recommended"]}

    # 更新已有的：still_recommended + last_checked_date
    for code, rec in existing.items():
        rec["still_recommended"] = code in strong_codes
        rec["last_checked_date"] = checked_date
        # 名称缺失时用报告补全
        if code in name_map and not rec.get("name"):
            rec["name"] = name_map[code]

    # 追加新进的
    for code in strong_codes:
        if code not in existing:
            existing[code] = {
                "code": code,
                "name": name_map.get(code, code),
                "first_recommended_date": checked_date,
                "score_at_recommend": 4,
                "still_recommended": True,
                "last_checked_date": checked_date,
            }

    # 按首次推荐日期排序（旧的在前）
    wl["recommended"] = sorted(
        existing.values(),
        key=lambda r: r.get("first_recommended_date", ""),
    )
    save_watchlist(wl, path)
    return wl
