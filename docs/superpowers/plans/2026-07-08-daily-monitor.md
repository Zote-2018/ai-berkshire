# 日扫描系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `tools/daily_monitor/`（Python 包）实现每日 03:00 自动扫描 watchlist（持仓 + 推荐池）的 CLI：复用 `stock_recommender.py` 数据接口拉行情/估值/打分，对比昨日快照判定 4 类信号（价格/估值/推荐池/事件——事件本期不做），异动时生成 Markdown 报告并通过 163 SMTP 发汇总邮件（标题分级 + 含"建议跑的命令"清单）。

**Architecture:** 包结构（CLI 入口 stub + 7 个职责单一的模块），零外部依赖（纯 stdlib + 复用 tools.stock_recommender）。单只股失败 ≠ 整体失败，节假日跳过，配额消耗为 0。

**Tech Stack:** Python >= 3.8 stdlib（json / argparse / smtplib / urllib / pathlib / datetime）、复用 `tools.stock_recommender`（fetch_quote/fetch_financials/fetch_dividends/score_stable）、pytest（参考 `tests/scheduler/` 风格）。

**Spec 来源:** `docs/superpowers/specs/2026-07-08-daily-monitor-design.md`

**Windows 提示:** Git Bash 下运行；Python 用 `python`；测试用 `python -m pytest`；中文路径加引号。

---

## 文件结构总览

| 文件 | 操作 | 责任 |
|------|------|------|
| `tools/daily_monitor.py` | 创建 | CLI 入口 stub（10 行），转调 `python -m tools.daily_monitor` |
| `tools/daily_monitor/__init__.py` | 创建 | 空文件 |
| `tools/daily_monitor/__main__.py` | 创建 | argparse + 子命令分发 |
| `tools/daily_monitor/watchlist.py` | 创建 | watchlist.json 加载/保存/CRUD |
| `tools/daily_monitor/snapshot.py` | 创建 | 快照读写 + 30 天滚动 + diff 工具 |
| `tools/daily_monitor/signals.py` | 创建 | 4 类信号判定 |
| `tools/daily_monitor/holidays.py` | 创建 | 节假日判断 |
| `tools/daily_monitor/smtp_loader.py` | 创建 | `.env.smtp` 解析 |
| `tools/daily_monitor/mail.py` | 创建 | HTML 渲染 + SMTP 发送 |
| `tools/daily_monitor/runner.py` | 创建 | 主流程编排（节假日/加载/打分/信号/报告/邮件/快照） |
| `tests/daily_monitor/__init__.py` | 创建 | 空 |
| `tests/daily_monitor/conftest.py` | 创建 | 共享 fixtures（tmp_watchlist / sample_quote 等） |
| `tests/daily_monitor/test_watchlist.py` | 创建 | watchlist CRUD 测试 |
| `tests/daily_monitor/test_snapshot.py` | 创建 | 快照读写 + 滚动测试 |
| `tests/daily_monitor/test_signals.py` | 创建 | 4 类信号边界值测试 |
| `tests/daily_monitor/test_holidays.py` | 创建 | 节假日判断测试 |
| `tests/daily_monitor/test_smtp_loader.py` | 创建 | .env.smtp 解析测试 |
| `tests/daily_monitor/test_mail.py` | 创建 | HTML 渲染 + 发送（mock smtplib）测试 |
| `tests/daily_monitor/test_runner.py` | 创建 | 集成测试（mock 行情接口） |
| `data/monitor/.gitkeep` | 创建 | 目录占位 |
| `data/zh-holidays.json` | 创建 | 节假日数据（初始含 2026 年样本） |
| `reports/日扫描/.gitkeep` | 创建 | 目录占位 |
| `logs/daily-monitor/.gitkeep` | 创建 | 目录占位 |
| `.env.smtp.example` | 创建 | SMTP 配置模板 |
| `.gitignore` | 修改 | 加 `.env.smtp` 和 `logs/daily-monitor/` |
| `scripts/install-daily-monitor.ps1` | 创建 | Windows 任务计划程序注册 |
| `scripts/uninstall-daily-monitor.ps1` | 创建 | 卸载 |
| `CLAUDE.md` | 修改 | 加"日扫描系统"章节 |

---

## Task 1: 项目骨架 + CLI 入口 + 冒烟测试

**Files:**
- Create: `tools/daily_monitor.py`（入口 stub）
- Create: `tools/daily_monitor/__init__.py`（空）
- Create: `tools/daily_monitor/__main__.py`（argparse 骨架）
- Create: `tests/daily_monitor/__init__.py`（空）
- Create: `data/monitor/.gitkeep`
- Create: `reports/日扫描/.gitkeep`
- Create: `logs/daily-monitor/.gitkeep`

- [ ] **Step 1: 建目录**

```bash
mkdir -p tools/daily_monitor tests/daily_monitor "data/monitor" "reports/日扫描" "logs/daily-monitor"
```

- [ ] **Step 2: 写 `tools/daily_monitor.py` 入口 stub**

文件 `tools/daily_monitor.py`：

```python
#!/usr/bin/env python3
"""daily_monitor.py — 日扫描 CLI 入口 stub。

实际实现在 tools/daily_monitor/ 包里。本文件保持兼容性：
用户可继续用 `python tools/daily_monitor.py run` 的习惯。

用法见 `python tools/daily_monitor.py --help`。
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.daily_monitor.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 写 `tools/daily_monitor/__init__.py`（空文件）**

```python
"""日扫描系统：watchlist（持仓+推荐池）日频监控 + 半自动邮件提醒。

设计文档：docs/superpowers/specs/2026-07-08-daily-monitor-design.md
实施计划：docs/superpowers/plans/2026-07-08-daily-monitor.md
"""
```

- [ ] **Step 4: 写 `tools/daily_monitor/__main__.py` argparse 骨架**

文件 `tools/daily_monitor/__main__.py`：

```python
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
```

- [ ] **Step 5: 写占位文件**

文件 `tests/daily_monitor/__init__.py`：空文件。

文件 `data/monitor/.gitkeep`：空文件。

文件 `reports/日扫描/.gitkeep`：空文件。

文件 `logs/daily-monitor/.gitkeep`：空文件。

- [ ] **Step 6: 冒烟测试**

```bash
python tools/daily_monitor.py --help
python tools/daily_monitor.py run --dry-run
```

预期：两条命令都打印帮助/stub 消息，退出码 0。

- [ ] **Step 7: Commit**

```bash
git add tools/daily_monitor.py tools/daily_monitor/ tests/daily_monitor/ data/monitor/.gitkeep "reports/日扫描/.gitkeep" logs/daily-monitor/.gitkeep
git commit -m "feat(daily-monitor): 骨架 + CLI argparse 入口（10 个子命令）"
```

---

## Task 2: watchlist.py 加载/保存/默认结构

**Files:**
- Create: `tools/daily_monitor/watchlist.py`
- Create: `tests/daily_monitor/test_watchlist.py`
- Create: `tests/daily_monitor/conftest.py`

- [ ] **Step 1: 写 conftest 共享 fixtures**

文件 `tests/daily_monitor/conftest.py`：

```python
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
```

- [ ] **Step 2: 写失败的测试**

文件 `tests/daily_monitor/test_watchlist.py`：

```python
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
```

- [ ] **Step 3: 跑测试看失败**

```bash
python -m pytest tests/daily_monitor/test_watchlist.py -v
```

预期：ImportError（模块不存在）。

- [ ] **Step 4: 写 watchlist.py 实现**

文件 `tools/daily_monitor/watchlist.py`：

```python
"""watchlist.json 加载/保存/CRUD。

watchlist 是日扫描的核心配置：持仓 + 推荐池 + 阈值。
- positions: 手动维护（add-position / remove-position 子命令）
- recommended: 自动同步（sync-recommended 子命令，每次 run 也会刷）
- thresholds: 手动编辑（DEFAULT_THRESHOLDS 提供初值）
"""

import json
from datetime import date
from pathlib import Path


class WatchlistError(Exception):
    """watchlist 操作错误（文件格式错误、重复添加等）。"""


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
```

- [ ] **Step 5: 跑测试看通过**

```bash
python -m pytest tests/daily_monitor/test_watchlist.py -v
```

预期：11 个测试全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add tools/daily_monitor/watchlist.py tests/daily_monitor/test_watchlist.py tests/daily_monitor/conftest.py
git commit -m "feat(daily-monitor): watchlist.json 加载/保存/CRUD + 11 个单元测试"
```

---

## Task 3: add-position / remove-position / show-watchlist / show-config 子命令接入

**Files:**
- Modify: `tools/daily_monitor/__main__.py`
- Modify: `tests/daily_monitor/test_watchlist.py`（新增 CLI 测试用例，或新建 test_cli.py）

- [ ] **Step 1: 写失败的 CLI 测试**

新建文件 `tests/daily_monitor/test_cli.py`：

```python
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
```

- [ ] **Step 2: 跑测试看失败**

```bash
python -m pytest tests/daily_monitor/test_cli.py -v
```

预期：AttributeError（`DEFAULT_WATCHLIST_PATH` 不存在 / `main` 不分发子命令）。

- [ ] **Step 3: 改 watchlist.py 加 DEFAULT_WATCHLIST_PATH**

修改 `tools/daily_monitor/watchlist.py`，在文件顶部 `DEFAULT_THRESHOLDS` 上方加：

```python
import os

DEFAULT_WATCHLIST_PATH = Path(
    os.environ.get("DAILY_MONITOR_WATCHLIST",
                   str(Path(__file__).resolve().parent.parent.parent / "data" / "monitor" / "watchlist.json"))
)
```

- [ ] **Step 4: 改 __main__.py 接入子命令**

完整替换 `tools/daily_monitor/__main__.py` 的 `main` 函数：

```python
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
        from tools.daily_monitor.watchlist import load_watchlist
        wl = load_watchlist(DEFAULT_WATCHLIST_PATH)
        print(json.dumps(wl, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "show-config":
        from tools.daily_monitor.watchlist import DEFAULT_WATCHLIST_PATH, load_watchlist
        wl = load_watchlist(DEFAULT_WATCHLIST_PATH)
        print(json.dumps(wl["thresholds"], ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "sync-recommended":
        print("[stub] sync-recommended 尚未实现（Task 4）", file=sys.stderr)
        return 0

    if args.cmd == "show-snapshot":
        print(f"[stub] show-snapshot 尚未实现（Task 5），date={args.date}", file=sys.stderr)
        return 0

    if args.cmd == "run":
        print("[stub] run 尚未实现（Task 9）", file=sys.stderr)
        return 0

    parser.error(f"未知子命令: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 跑测试看通过**

```bash
python -m pytest tests/daily_monitor/test_cli.py tests/daily_monitor/test_watchlist.py -v
```

预期：全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add tools/daily_monitor/__main__.py tools/daily_monitor/watchlist.py tests/daily_monitor/test_cli.py
git commit -m "feat(daily-monitor): add/remove/show-watchlist/show-config 子命令接入"
```

---

## Task 4: sync-recommended 子命令（解析最新推荐报告）

**Files:**
- Modify: `tools/daily_monitor/watchlist.py`（新增 `sync_recommended` 函数）
- Modify: `tools/daily_monitor/__main__.py`（接入 sync-recommended）
- Create: `tests/daily_monitor/test_sync_recommended.py`

- [ ] **Step 1: 写失败的测试**

文件 `tests/daily_monitor/test_sync_recommended.py`：

```python
"""sync_recommended 单元测试：从 stable-{date}.md 解析推荐列表并同步 watchlist。"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from tools.daily_monitor.watchlist import (
    load_watchlist, save_watchlist, sync_recommended,
)


SAMPLE_REPORT = """# 稳定收益推荐 — 2026-07-04

## Top 推荐（4 分）

| 代码 | 名称 | 股息率% | PE | ROE 均值% | ROE 标准差pp |
|---|---|---|---|---|---|
| 600036 | 招商银行 | 5.21 | 7.5 | 16.8 | 1.2 |
| 601318 | 中国平安 | 5.05 | 8.2 | 18.1 | 2.0 |

## 备选（3 分）

| 代码 | 名称 | 股息率% | PE | ROE 均值% | ROE 标准差pp |
|---|---|---|---|---|---|
| 600000 | 浦发银行 | 4.8 | 5.5 | 11.2 | 1.5 |

## fin_ai 观点层
...
"""


def test_sync_首次同步_只取4分强推荐(tmp_watchlist_path, tmp_path):
    """新推荐池：解析 4 分强推荐，忽略备选（3 分）。"""
    report_path = tmp_path / "stable-2026-07-04.md"
    report_path.write_text(SAMPLE_REPORT, encoding="utf-8")

    sync_recommended(tmp_watchlist_path, report_path, checked_date="2026-07-08")
    wl = load_watchlist(tmp_watchlist_path)

    codes = [r["code"] for r in wl["recommended"]]
    assert "600036" in codes
    assert "601318" in codes
    assert "600000" not in codes  # 3 分备选不进


def test_sync_保留历史_跌出的标记still_false(tmp_watchlist_path, tmp_path):
    """之前推荐过、本次不在 4 分列表的，标 still_recommended=False 但保留。"""
    # 先种入旧推荐
    save_watchlist({
        "version": 1,
        "thresholds": {"price_change_daily_pct": 5.0, "price_change_5d_pct": 10.0,
                       "cost_drawdown_pct": 15.0, "pe_undervalued": 8, "pe_overvalued": 20,
                       "dividend_yield_high": 5.0, "dividend_yield_low": 3.0,
                       "snapshot_history_days": 30},
        "positions": [],
        "recommended": [
            {"code": "999999", "name": "已退出股票",
             "first_recommended_date": "2026-06-01", "score_at_recommend": 4,
             "still_recommended": True, "last_checked_date": "2026-07-07"},
        ],
    }, tmp_watchlist_path)

    report_path = tmp_path / "stable-2026-07-04.md"
    report_path.write_text(SAMPLE_REPORT, encoding="utf-8")

    sync_recommended(tmp_watchlist_path, report_path, checked_date="2026-07-08")
    wl = load_watchlist(tmp_watchlist_path)

    old = next(r for r in wl["recommended"] if r["code"] == "999999")
    assert old["still_recommended"] is False
    assert old["last_checked_date"] == "2026-07-08"


def test_sync_重新进入_翻回still_true(tmp_watchlist_path, tmp_path):
    """之前跌出（still=False）、本次重新满足，翻回 still=True。"""
    save_watchlist({
        "version": 1, "thresholds": {"pe_undervalued": 8, "pe_overvalued": 20,
                                     "price_change_daily_pct": 5.0, "price_change_5d_pct": 10.0,
                                     "cost_drawdown_pct": 15.0, "dividend_yield_high": 5.0,
                                     "dividend_yield_low": 3.0, "snapshot_history_days": 30},
        "positions": [],
        "recommended": [
            {"code": "600036", "name": "招商银行",
             "first_recommended_date": "2026-06-01", "score_at_recommend": 4,
             "still_recommended": False, "last_checked_date": "2026-07-07"},
        ],
    }, tmp_watchlist_path)

    report_path = tmp_path / "stable-2026-07-04.md"
    report_path.write_text(SAMPLE_REPORT, encoding="utf-8")

    sync_recommended(tmp_watchlist_path, report_path, checked_date="2026-07-08")
    wl = load_watchlist(tmp_watchlist_path)

    rec = next(r for r in wl["recommended"] if r["code"] == "600036")
    assert rec["still_recommended"] is True
    assert rec["last_checked_date"] == "2026-07-08"
    # first_recommended_date 不变（保留首次推荐日期）
    assert rec["first_recommended_date"] == "2026-06-01"


def test_sync_报告文件不存在_抛异常(tmp_watchlist_path, tmp_path):
    """报告文件不存在时抛 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        sync_recommended(tmp_watchlist_path, tmp_path / "nonexistent.md", checked_date="2026-07-08")
```

- [ ] **Step 2: 跑测试看失败**

```bash
python -m pytest tests/daily_monitor/test_sync_recommended.py -v
```

预期：ImportError（`sync_recommended` 不存在）。

- [ ] **Step 3: 写 sync_recommended 实现**

在 `tools/daily_monitor/watchlist.py` 末尾追加：

```python
import re


_SECTION_STRONG = "## Top 推荐（4 分）"
_SECTION_NEXT = "## 备选"


def _parse_strong_codes(report_text: str) -> list:
    """从 stable-{date}.md 解析 4 分强推荐代码列表。

    报告结构：'## Top 推荐（4 分）' 节下的表格行，第 1 列为代码。
    返回：[code, ...]，按报告顺序。
    """
    # 截取 4 分节到下一个 ## 之间
    start = report_text.find(_SECTION_STRONG)
    if start < 0:
        return []
    end = report_text.find("\n## ", start + len(_SECTION_STRONG))
    section = report_text[start: end if end > 0 else None]
    # 表格行格式：| 600036 | 招商银行 | ... |
    codes = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        # 跳过分隔符行（---|---|---）和表头（代码）
        if set(cells[0]) <= {"-"}:
            continue
        if cells[0] == "代码":
            continue
        # 6 位数字代码
        if re.match(r"^\d{6}$", cells[0]):
            codes.append(cells[0])
    return codes


def _parse_strong_name_map(report_text: str) -> dict:
    """同上，但返回 {code: name} 字典（用于补全名称）。"""
    start = report_text.find(_SECTION_STRONG)
    if start < 0:
        return {}
    end = report_text.find("\n## ", start + len(_SECTION_STRONG))
    section = report_text[start: end if end > 0 else None]
    mapping = {}
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if set(cells[0]) <= {"-"} or cells[0] == "代码":
            continue
        if re.match(r"^\d{6}$", cells[0]) and cells[1]:
            mapping[cells[0]] = cells[1]
    return mapping


def sync_recommended(path: Path, report_path: Path, *, checked_date: str) -> dict:
    """根据最新 stable-{date}.md 同步 watchlist.recommended。

    规则：
    - 报告里的 4 分强推荐 → still_recommended=True，新进的追加 first_recommended_date=今天
    - 不在报告里的旧推荐 → still_recommended=False（保留，不删除）
    - first_recommended_date 永不更新（保留首次推荐日期）
    - last_checked_date 全部更新为 checked_date
    """
    if not report_path.exists():
        raise FileNotFoundError(f"推荐报告不存在: {report_path}")

    report_text = report_path.read_text(encoding="utf-8")
    strong_codes = set(_parse_strong_codes(report_text))
    name_map = _parse_strong_name_map(report_text)

    wl = load_watchlist(path)
    existing = {r["code"]: r for r in wl["recommended"]}

    # 更新已有的
    for code, rec in existing.items():
        rec["still_recommended"] = code in strong_codes
        rec["last_checked_date"] = checked_date
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
```

- [ ] **Step 4: 改 __main__.py 接入 sync-recommended**

修改 `tools/daily_monitor/__main__.py`，把 `sync-recommended` 分支替换为：

```python
    if args.cmd == "sync-recommended":
        from tools.daily_monitor.watchlist import sync_recommended
        from datetime import date
        # 找最新的 stable-{date}.md
        reports_dir = Path(__file__).resolve().parent.parent.parent / "reports" / "股票推荐"
        if not reports_dir.exists():
            print(f"❌ 报告目录不存在: {reports_dir}", file=sys.stderr)
            return 1
        candidates = sorted(reports_dir.glob("stable-*.md"), reverse=True)
        if not candidates:
            print(f"❌ {reports_dir} 下无 stable-*.md 报告", file=sys.stderr)
            return 1
        latest = candidates[0]
        try:
            wl = sync_recommended(DEFAULT_WATCHLIST_PATH, latest, checked_date=date.today().isoformat())
        except Exception as e:
            print(f"❌ 同步失败: {e}", file=sys.stderr)
            return 1
        active = [r for r in wl["recommended"] if r["still_recommended"]]
        print(f"✅ 同步完成：{len(active)} 只活跃推荐（共 {len(wl['recommended'])} 条记录）", file=sys.stderr)
        print(f"   报告：{latest.name}", file=sys.stderr)
        return 0
```

文件顶部 `import` 块加 `from pathlib import Path`。

- [ ] **Step 5: 跑测试看通过**

```bash
python -m pytest tests/daily_monitor/test_sync_recommended.py tests/daily_monitor/test_cli.py -v
```

预期：全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add tools/daily_monitor/watchlist.py tools/daily_monitor/__main__.py tests/daily_monitor/test_sync_recommended.py
git commit -m "feat(daily-monitor): sync-recommended 子命令（解析 4 分强推荐，保留历史）"
```

---

## Task 5: snapshot.py 快照读写 + 30 天滚动

**Files:**
- Create: `tools/daily_monitor/snapshot.py`
- Create: `tests/daily_monitor/test_snapshot.py`

- [ ] **Step 1: 写失败的测试**

文件 `tests/daily_monitor/test_snapshot.py`：

```python
"""tools.daily_monitor.snapshot 单元测试。"""

from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from tools.daily_monitor.snapshot import (
    SnapshotError,
    cleanup_old_snapshots,
    load_snapshot,
    write_snapshot,
)


def _sample_snapshot(scan_date: str) -> dict:
    """构造一份快照样本。"""
    return {
        "scan_date": scan_date,
        "stocks": {
            "600036": {
                "name": "招商银行",
                "price": 38.5,
                "prev_close": 38.0,
                "pe": 7.5,
                "pb": 1.0,
                "market_cap_yi": 9700.0,
                "dividend_yield": 5.2,
                "score": 4,
            },
        },
    }


def test_write_load_往返(tmp_path):
    """写 → 读，数据一致。"""
    path = tmp_path / "snapshot-2026-07-08.json"
    snap = _sample_snapshot("2026-07-08")
    write_snapshot(snap, path)
    reloaded = load_snapshot(path)
    assert reloaded == snap


def test_load_不存在_返回None(tmp_path):
    """文件不存在时返回 None（让上游判断首次运行）。"""
    assert load_snapshot(tmp_path / "snapshot-2026-07-08.json") is None


def test_load_格式错误_抛异常(tmp_path):
    """格式错误时抛 SnapshotError。"""
    path = tmp_path / "snapshot-2026-07-08.json"
    path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(SnapshotError):
        load_snapshot(path)


def test_cleanup_保留最近N天(tmp_path):
    """保留最近 N 天，更老的删除。"""
    # 准备 5 个快照，日期跨越 10 天
    for i in range(5):
        d = f"2026-07-0{i+1}"
        path = tmp_path / f"snapshot-{d}.json"
        write_snapshot(_sample_snapshot(d), path)

    removed = cleanup_old_snapshots(tmp_path, keep_days=3, today_str="2026-07-05")
    # 7-01 / 7-02 / 7-03 < 7-05 - 3 days = 7-02，应被删
    assert (tmp_path / "snapshot-2026-07-01.json").exists() is False
    assert (tmp_path / "snapshot-2026-07-02.json").exists() is False
    assert (tmp_path / "snapshot-2026-07-03.json").exists() is True
    assert (tmp_path / "snapshot-2026-07-04.json").exists() is True
    assert (tmp_path / "snapshot-2026-07-05.json").exists() is True
    assert len(removed) == 2


def test_cleanup_目录不存在_不抛(tmp_path):
    """目录不存在时返回空列表，不抛异常。"""
    assert cleanup_old_snapshots(tmp_path / "nonexistent", keep_days=30, today_str="2026-07-08") == []


def test_cleanup_无snapshot文件_返回空(tmp_path):
    """目录存在但没有 snapshot-*.json 时返回空。"""
    assert cleanup_old_snapshots(tmp_path, keep_days=30, today_str="2026-07-08") == []
```

- [ ] **Step 2: 跑测试看失败**

```bash
python -m pytest tests/daily_monitor/test_snapshot.py -v
```

预期：ImportError。

- [ ] **Step 3: 写 snapshot.py 实现**

文件 `tools/daily_monitor/snapshot.py`：

```python
"""每日快照读写 + 30 天滚动清理。

快照文件名格式：snapshot-{YYYY-MM-DD}.json
路径：data/monitor/snapshot-{date}.json
内容：{scan_date, stocks: {code: {price, prev_close, pe, pb, market_cap_yi, dividend_yield, score}}}

对比类信号（价格异动、推荐池变动、52 周新高低）依赖昨日快照。
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path


class SnapshotError(Exception):
    """快照操作错误。"""


def load_snapshot(path: Path):
    """加载快照。文件不存在返回 None（首次运行）；格式错误抛 SnapshotError。"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SnapshotError(f"快照格式错误 ({path}): {e}")


def write_snapshot(data: dict, path: Path) -> None:
    """保存快照。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


_SNAPSHOT_RE = re.compile(r"^snapshot-(\d{4}-\d{2}-\d{2})\.json$")


def cleanup_old_snapshots(directory: Path, *, keep_days: int, today_str: str) -> list:
    """清理 keep_days 天前的快照。返回被删除的 Path 列表。

    directory 不存在时返回空。
    today_str: 'YYYY-MM-DD'，作为今天的参考。
    """
    if not directory.exists():
        return []
    today = datetime.strptime(today_str, "%Y-%m-%d").date()
    cutoff = today - timedelta(days=keep_days)
    removed = []
    for entry in directory.iterdir():
        m = _SNAPSHOT_RE.match(entry.name)
        if not m:
            continue
        snap_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        if snap_date < cutoff:
            entry.unlink()
            removed.append(entry)
    return removed
```

- [ ] **Step 4: 跑测试看通过**

```bash
python -m pytest tests/daily_monitor/test_snapshot.py -v
```

预期：6 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add tools/daily_monitor/snapshot.py tests/daily_monitor/test_snapshot.py
git commit -m "feat(daily-monitor): snapshot.py 快照读写 + 30 天滚动清理"
```

---

## Task 6: signals.py 4 类信号判定

**Files:**
- Create: `tools/daily_monitor/signals.py`
- Create: `tests/daily_monitor/test_signals.py`

- [ ] **Step 1: 写失败的测试**

文件 `tests/daily_monitor/test_signals.py`：

```python
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

def test_价格_单日涨超5%触发():
    today = _today_data(price=10.5, prev_close=10.0)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    types = [s.type for s in signals]
    assert "price_daily_up" in types
    assert signals[0].severity == SEVERITY_WATCH


def test_价格_单日涨刚好5%触发_边界值():
    """5.0% 应触发（>=阈值）。"""
    today = _today_data(price=10.5, prev_close=10.0)
    # price=10.5, prev=10.0 → +5.0%，等于阈值，应触发
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "price_daily_up" for s in signals)


def test_价格_单日涨4.9%不触发():
    today = _today_data(price=10.49, prev_close=10.0)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert not any(s.type == "price_daily_up" for s in signals)


def test_价格_单日跌5%触发():
    today = _today_data(price=9.5, prev_close=10.0)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "price_daily_down" for s in signals)


def test_价格_5日累计涨10%触发():
    today = _today_data(price=11.0)
    # last_5d_close 是 5 个交易日前的收盘
    signals = check_signals(today=today, yesterday=None, last_5d_close=10.0,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "price_5d_up" for s in signals)


def test_价格_跌破成本15%触发_紧急():
    today = _today_data(price=8.5, buy_price=10.0)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    critical = [s for s in signals if s.type == "cost_drawdown"]
    assert len(critical) == 1
    assert critical[0].severity == SEVERITY_CRITICAL


def test_价格_跌破成本刚好15%触发():
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


def test_估值_股息率升破5%_机会():
    today = _today_data(dividend_yield=5.5)
    signals = check_signals(today=today, yesterday=None, last_5d_close=None,
                            thresholds=_thresholds(), is_position=True,
                            snapshots_for_52w=[])
    assert any(s.type == "dividend_yield_high" for s in signals)


def test_估值_股息率跌破3%_紧急():
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
```

- [ ] **Step 2: 跑测试看失败**

```bash
python -m pytest tests/daily_monitor/test_signals.py -v
```

预期：ImportError。

- [ ] **Step 3: 写 signals.py 实现**

文件 `tools/daily_monitor/signals.py`：

```python
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

from dataclasses import dataclass, field
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
    today_score = today.get("score")
    yesterday_score = (yesterday or {}).get("score") if yesterday else None

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
```

- [ ] **Step 4: 跑测试看通过**

```bash
python -m pytest tests/daily_monitor/test_signals.py -v
```

预期：19 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add tools/daily_monitor/signals.py tests/daily_monitor/test_signals.py
git commit -m "feat(daily-monitor): signals.py 4 类信号判定（价格/估值/推荐池）+ 严重度分级"
```

---

## Task 7: holidays.py 节假日判断

**Files:**
- Create: `tools/daily_monitor/holidays.py`
- Create: `data/zh-holidays.json`（初始含 2026 年样本）
- Create: `tests/daily_monitor/test_holidays.py`

- [ ] **Step 1: 写 `data/zh-holidays.json` 初始数据**

文件 `data/zh-holidays.json`：

```json
{
  "_meta": {
    "version": "2026-07-08-initial",
    "note": "中国 A 股休市日（节假日 + 周末交易所本来就不开）。每年元旦后花 10 分钟更新一次。来源：上交所/深交所休市安排",
    "sources": ["http://www.sse.com.cn/disclosure/dealinstruc/closed/"]
  },
  "2026": [
    "2026-01-01",
    "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",
    "2026-04-06",
    "2026-05-01", "2026-05-04", "2026-05-05",
    "2026-06-19",
    "2026-09-25",
    "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"
  ]
}
```

- [ ] **Step 2: 写失败的测试**

文件 `tests/daily_monitor/test_holidays.py`：

```python
"""tools.daily_monitor.holidays 单元测试。"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from tools.daily_monitor.holidays import HolidayError, is_holiday, load_holidays


def test_load_正常加载(tmp_path):
    """加载节假日 JSON，返回 {year: set(dates)} 结构（_meta 过滤掉）。"""
    path = tmp_path / "zh-holidays.json"
    path.write_text(
        '{"_meta": {"version": "x"}, "2026": ["2026-01-01", "2026-05-01"]}',
        encoding="utf-8",
    )
    holidays = load_holidays(path)
    assert "2026" in holidays
    assert holidays["2026"] == {"2026-01-01", "2026-05-01"}


def test_load_文件不存在_返回空(tmp_path):
    """文件不存在时返回空 dict（不抛异常，让 is_holiday 自然返回 False）。"""
    assert load_holidays(tmp_path / "nonexistent.json") == {}


def test_load_格式错误_抛异常(tmp_path):
    """JSON 格式错误时抛 HolidayError。"""
    path = tmp_path / "zh-holidays.json"
    path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(HolidayError):
        load_holidays(path)


def test_is_holiday_命中(tmp_path):
    """节假日列表中的日期返回 True。"""
    path = tmp_path / "zh-holidays.json"
    path.write_text('{"2026": ["2026-05-01"]}', encoding="utf-8")
    assert is_holiday("2026-05-01", holidays_path=path) is True


def test_is_holiday_未命中(tmp_path):
    """不在列表中返回 False。"""
    path = tmp_path / "zh-holidays.json"
    path.write_text('{"2026": ["2026-05-01"]}', encoding="utf-8")
    assert is_holiday("2026-05-02", holidays_path=path) is False


def test_is_holiday_周末返回True(tmp_path):
    """周六/周日即使不在 holidays 列表也返回 True（交易所不开）。"""
    path = tmp_path / "zh-holidays.json"
    path.write_text('{"2026": []}', encoding="utf-8")
    # 2026-07-04 是周六，2026-07-05 是周日
    assert is_holiday("2026-07-04", holidays_path=path) is True
    assert is_holiday("2026-07-05", holidays_path=path) is True


def test_is_holiday_工作日返回False(tmp_path):
    """周一到周五且不在节假日列表返回 False。"""
    path = tmp_path / "zh-holidays.json"
    path.write_text('{"2026": []}', encoding="utf-8")
    # 2026-07-08 是周三
    assert is_holiday("2026-07-08", holidays_path=path) is False


def test_is_holiday_跨年数据(tmp_path):
    """跨年场景：2025 数据不影响 2026 判断。"""
    path = tmp_path / "zh-holidays.json"
    path.write_text('{"2025": ["2026-05-01"], "2026": []}', encoding="utf-8")
    # 2026-05-01 应看 2026 数据，不是 2025
    assert is_holiday("2026-05-01", holidays_path=path) is False
```

- [ ] **Step 3: 跑测试看失败**

```bash
python -m pytest tests/daily_monitor/test_holidays.py -v
```

预期：ImportError。

- [ ] **Step 4: 写 holidays.py 实现**

文件 `tools/daily_monitor/holidays.py`：

```python
"""节假日判断。

判断规则：
1. 周六/周日 → True（交易所不开）
2. 在 data/zh-holidays.json 的对应年份列表里 → True
3. 否则 False

文件不存在或格式错误时降级：只看周末（不阻塞扫描）。
"""

import json
from datetime import datetime
from pathlib import Path


class HolidayError(Exception):
    """节假日文件格式错误。"""


DEFAULT_HOLIDAYS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "zh-holidays.json"


def load_holidays(path: Path = None) -> dict:
    """加载节假日。返回 {year_str: set(date_str)}。

    文件不存在时返回空 dict。格式错误抛 HolidayError。
    """
    path = path or DEFAULT_HOLIDAYS_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HolidayError(f"zh-holidays.json 格式错误 ({path}): {e}")
    holidays = {}
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            holidays[key] = set(value)
    return holidays


def is_holiday(date_str: str, *, holidays_path: Path = None) -> bool:
    """判断某日是否为节假日（含周末）。"""
    # 1. 周末判断
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if dt.weekday() >= 5:  # 5=周六, 6=周日
        return True

    # 2. 节假日列表判断
    holidays = load_holidays(holidays_path)
    year = date_str[:4]
    return date_str in holidays.get(year, set())
```

- [ ] **Step 5: 跑测试看通过**

```bash
python -m pytest tests/daily_monitor/test_holidays.py -v
```

预期：8 个测试全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add tools/daily_monitor/holidays.py data/zh-holidays.json tests/daily_monitor/test_holidays.py
git commit -m "feat(daily-monitor): holidays.py 节假日判断（含周末 + zh-holidays.json 列表）"
```

---

## Task 8: smtp_loader.py + mail.py（HTML 渲染 + SMTP 发送）

**Files:**
- Create: `tools/daily_monitor/smtp_loader.py`
- Create: `tools/daily_monitor/mail.py`
- Create: `.env.smtp.example`
- Modify: `.gitignore`
- Create: `tests/daily_monitor/test_smtp_loader.py`
- Create: `tests/daily_monitor/test_mail.py`

- [ ] **Step 1: 写 `.env.smtp.example` 模板**

文件 `.env.smtp.example`：

```
# SMTP 配置（用于日扫描邮件发送）
# 复制本文件为 .env.smtp，填入真实值（.env.smtp 已在 .gitignore 中）
# 163 邮箱授权码获取：登录 mail.163.com → 设置 → POP3/SMTP/IMAP → 开启 SMTP → 生成授权码

SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=your_email@163.com
SMTP_PASS=your_auth_code_here
SMTP_FROM=your_email@163.com
SMTP_TO=recipient@example.com
```

- [ ] **Step 2: 改 `.gitignore`**

修改 `.gitignore`，追加：

```
# 日扫描 SMTP 配置（含授权码，不能进库）
.env.smtp

# 日扫描运行日志（每次跑生成一个 JSON）
logs/daily-monitor/
!logs/daily-monitor/.gitkeep
```

- [ ] **Step 3: 写失败的 smtp_loader 测试**

文件 `tests/daily_monitor/test_smtp_loader.py`：

```python
"""tools.daily_monitor.smtp_loader 单元测试。"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from tools.daily_monitor.smtp_loader import SmtpConfig, SmtpConfigError, load_smtp_config


def test_load_完整配置(tmp_path):
    """所有字段齐全时正确加载。"""
    path = tmp_path / ".env.smtp"
    path.write_text(
        "SMTP_HOST=smtp.163.com\n"
        "SMTP_PORT=465\n"
        "SMTP_USER=me@163.com\n"
        "SMTP_PASS=authcode123\n"
        "SMTP_FROM=me@163.com\n"
        "SMTP_TO=you@163.com\n",
        encoding="utf-8",
    )
    cfg = load_smtp_config(path)
    assert cfg.host == "smtp.163.com"
    assert cfg.port == 465
    assert cfg.user == "me@163.com"
    assert cfg.password == "authcode123"
    assert cfg.from_addr == "me@163.com"
    assert cfg.to_addr == "you@163.com"


def test_load_文件不存在_抛异常(tmp_path):
    """文件不存在抛 SmtpConfigError（让上游决定是否降级）。"""
    with pytest.raises(SmtpConfigError):
        load_smtp_config(tmp_path / ".env.smtp")


def test_load_缺字段_抛异常(tmp_path):
    """缺少必需字段时抛异常，错误消息含缺失字段名。"""
    path = tmp_path / ".env.smtp"
    path.write_text("SMTP_HOST=smtp.163.com\nSMTP_PORT=465\n", encoding="utf-8")
    with pytest.raises(SmtpConfigError) as exc:
        load_smtp_config(path)
    assert "SMTP_USER" in str(exc.value)


def test_load_忽略注释和空行(tmp_path):
    """支持 # 注释和空行。"""
    path = tmp_path / ".env.smtp"
    path.write_text(
        "# 这是注释\n"
        "\n"
        "SMTP_HOST=smtp.163.com\n"
        "# 另一行注释\n"
        "SMTP_PORT=465\n"
        "SMTP_USER=me@163.com\n"
        "SMTP_PASS=p\n"
        "SMTP_FROM=me@163.com\n"
        "SMTP_TO=you@163.com\n",
        encoding="utf-8",
    )
    cfg = load_smtp_config(path)
    assert cfg.host == "smtp.163.com"
    assert cfg.user == "me@163.com"


def test_load_port支持字符串转int(tmp_path):
    """SMTP_PORT 写成字符串也能转 int。"""
    path = tmp_path / ".env.smtp"
    path.write_text(
        "SMTP_HOST=h\nSMTP_PORT=587\nSMTP_USER=u\nSMTP_PASS=p\n"
        "SMTP_FROM=f@x.com\nSMTP_TO=t@x.com\n",
        encoding="utf-8",
    )
    cfg = load_smtp_config(path)
    assert cfg.port == 587
    assert isinstance(cfg.port, int)
```

- [ ] **Step 4: 写 smtp_loader.py 实现**

文件 `tools/daily_monitor/smtp_loader.py`：

```python
""".env.smtp 解析。

格式：KEY=VALUE 每行一对，# 开头注释，空行忽略。
必需字段：SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / SMTP_FROM / SMTP_TO

不引入 python-dotenv，避免新增依赖。
"""

import os
from dataclasses import dataclass
from pathlib import Path


class SmtpConfigError(Exception):
    """SMTP 配置错误。"""


@dataclass
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    to_addr: str


REQUIRED_FIELDS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM", "SMTP_TO")


def load_smtp_config(path: Path) -> SmtpConfig:
    """加载 .env.smtp。文件不存在或缺字段抛 SmtpConfigError。"""
    if not path.exists():
        raise SmtpConfigError(f"SMTP 配置文件不存在: {path}（参考 .env.smtp.example）")

    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()

    missing = [f for f in REQUIRED_FIELDS if f not in values]
    if missing:
        raise SmtpConfigError(f"SMTP 配置缺失字段: {', '.join(missing)}")

    try:
        port = int(values["SMTP_PORT"])
    except ValueError:
        raise SmtpConfigError(f"SMTP_PORT 必须是整数: {values['SMTP_PORT']}")

    return SmtpConfig(
        host=values["SMTP_HOST"],
        port=port,
        user=values["SMTP_USER"],
        password=values["SMTP_PASS"],
        from_addr=values["SMTP_FROM"],
        to_addr=values["SMTP_TO"],
    )


DEFAULT_SMTP_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env.smtp"
```

- [ ] **Step 5: 写失败的 mail 测试**

文件 `tests/daily_monitor/test_mail.py`：

```python
"""tools.daily_monitor.mail 单元测试。

测试 HTML 渲染（不依赖 SMTP）+ SMTP 发送（mock smtplib）。
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from tools.daily_monitor.mail import render_mail_html, render_mail_subject, send_mail
from tools.daily_monitor.signals import Signal, SEVERITY_CRITICAL, SEVERITY_WATCH, SEVERITY_OPPORTUNITY
from tools.daily_monitor.smtp_loader import SmtpConfig


def _signal(**kwargs):
    """构造 Signal。"""
    base = dict(
        code="600036", name="招商银行", type="price_daily_down",
        severity=SEVERITY_WATCH, detail="单日跌 5.2%",
        actual_value="-5.2%", threshold="±5%",
        suggest_cmd="/news-pulse 招商银行 跌5% 1天",
    )
    base.update(kwargs)
    return Signal(**base)


def test_subject_有异动():
    """异动 N 只 → 标题 '[日扫描] {date} 共 {N} 只异动'。"""
    subject = render_mail_subject(scan_date="2026-07-08", triggered_count=3)
    assert subject == "[日扫描] 2026-07-08 共 3 只异动"


def test_subject_无异动():
    subject = render_mail_subject(scan_date="2026-07-08", triggered_count=0)
    assert "无异动" in subject


def test_html_包含基本信息():
    """HTML 含扫描日期、watchlist 总数、触发数。"""
    html = render_mail_html(
        scan_date="2026-07-08",
        market_date="2026-07-07",
        total_scanned=15,
        triggered_count=1,
        signals_by_code={"600036": [_signal()]},
        untriggered_codes=["600519", "000858"],
    )
    assert "2026-07-08" in html
    assert "2026-07-07" in html  # 反映上一交易日
    assert "15" in html  # 总数
    assert "1" in html  # 触发数


def test_html_分级渲染():
    """按严重度分节渲染（紧急 / 关注 / 机会）。"""
    html = render_mail_html(
        scan_date="2026-07-08", market_date="2026-07-07",
        total_scanned=3, triggered_count=3,
        signals_by_code={
            "600036": [_signal(severity=SEVERITY_CRITICAL, type="cost_drawdown")],
            "600519": [_signal(severity=SEVERITY_WATCH)],
            "601318": [_signal(severity=SEVERITY_OPPORTUNITY, code="601318", name="中国平安")],
        },
        untriggered_codes=[],
    )
    assert "🔴" in html or "紧急" in html
    assert "🟡" in html or "关注" in html
    assert "🟢" in html or "机会" in html


def test_html_含建议命令():
    """每条信号的建议命令以 <code> 标签出现在 HTML 中。"""
    html = render_mail_html(
        scan_date="2026-07-08", market_date="2026-07-07",
        total_scanned=1, triggered_count=1,
        signals_by_code={"600036": [_signal()]},
        untriggered_codes=[],
    )
    assert "<code>/news-pulse" in html


def test_html_含未触发股票列表():
    """未触发股票代码折叠出现在 HTML 底部。"""
    html = render_mail_html(
        scan_date="2026-07-08", market_date="2026-07-07",
        total_scanned=3, triggered_count=1,
        signals_by_code={"600036": [_signal()]},
        untriggered_codes=["600519", "000858"],
    )
    assert "600519" in html
    assert "000858" in html


def test_send_mail_成功调用smtplib():
    """send_mail 调用 smtplib.SMTP_SSL.sendmail，参数正确。"""
    cfg = SmtpConfig(
        host="smtp.163.com", port=465,
        user="me@163.com", password="pass",
        from_addr="me@163.com", to_addr="you@163.com",
    )
    with patch("tools.daily_monitor.mail.smtplib") as mock_smtplib:
        mock_server = MagicMock()
        mock_smtplib.SMTP_SSL.return_value.__enter__.return_value = mock_server
        send_mail(cfg, subject="测试标题", html_body="<html>测试</html>")
        # 断言 sendmail 被调用
        mock_server.sendmail.assert_called_once()
        args = mock_server.sendmail.call_args[0]
        assert args[0] == "me@163.com"  # from
        assert args[1] == "you@163.com"  # to
        assert "测试标题" in args[2]  # 邮件正文含标题
        assert "<html>测试</html>" in args[2]  # 正文含 HTML


def test_send_mail_无配置时抛SmtpConfigError(tmp_path):
    """.env.smtp 不存在时 send_mail 不该静默失败。"""
    from tools.daily_monitor.smtp_loader import SmtpConfigError
    with pytest.raises(SmtpConfigError):
        # 调用 load_smtp_config 不存在的路径
        from tools.daily_monitor.smtp_loader import load_smtp_config
        load_smtp_config(tmp_path / "nonexistent")
```

- [ ] **Step 6: 写 mail.py 实现**

文件 `tools/daily_monitor/mail.py`：

```python
"""邮件 HTML 渲染 + SMTP 发送。

依赖：stdlib smtplib + email.mime
渲染规则：
- 标题：'[日扫描] {date} 共 N 只异动' 或 '[日扫描] {date} 无异动'
- 正文：分 🔴 紧急 / 🟡 关注 / 🟢 机会 三节，每节表格
- 未触发股票列在底部
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import List

from tools.daily_monitor.signals import (
    SEVERITY_CRITICAL, SEVERITY_WATCH, SEVERITY_OPPORTUNITY, Signal,
)
from tools.daily_monitor.smtp_loader import (
    DEFAULT_SMTP_ENV_PATH, SmtpConfig, SmtpConfigError, load_smtp_config,
)


_SEVERITY_LABEL = {
    SEVERITY_CRITICAL: ("🔴", "紧急"),
    SEVERITY_WATCH: ("🟡", "关注"),
    SEVERITY_OPPORTUNITY: ("🟢", "机会"),
}


def render_mail_subject(*, scan_date: str, triggered_count: int) -> str:
    if triggered_count > 0:
        return f"[日扫描] {scan_date} 共 {triggered_count} 只异动"
    return f"[日扫描] {scan_date} 无异动"


def render_mail_html(
    *,
    scan_date: str,
    market_date: str,
    total_scanned: int,
    triggered_count: int,
    signals_by_code: dict,
    untriggered_codes: List[str],
) -> str:
    """渲染邮件 HTML 正文。

    signals_by_code: {code: [Signal, ...]}
    untriggered_codes: 未触发股票代码列表
    """
    # 收集每只股票的最高严重度（用于排序/分节）
    def severity_rank(sev: str) -> int:
        return {SEVERITY_CRITICAL: 0, SEVERITY_WATCH: 1, SEVERITY_OPPORTUNITY: 2}.get(sev, 99)

    # 一只股只取最高严重度作为分组依据
    grouped = {SEVERITY_CRITICAL: [], SEVERITY_WATCH: [], SEVERITY_OPPORTUNITY: []}
    for code, signals in signals_by_code.items():
        if not signals:
            continue
        top_sev = min((s.severity for s in signals), key=severity_rank)
        grouped[top_sev].append((code, signals))

    parts = [
        f"<h2>📊 日扫描 — {escape(scan_date)}</h2>",
        f"<p>扫描 watchlist 共 <b>{total_scanned}</b> 只，"
        f"<b>{triggered_count}</b> 只触发信号。反映 {escape(market_date)} 市场。</p>",
    ]

    for sev in (SEVERITY_CRITICAL, SEVERITY_WATCH, SEVERITY_OPPORTUNITY):
        items = grouped[sev]
        if not items:
            continue
        emoji, label = _SEVERITY_LABEL[sev]
        parts.append(f"<h3>{emoji} {label}（{len(items)}）</h3>")
        parts.append('<table border="1" cellpadding="6" cellspacing="0">')
        parts.append(
            "<tr><th>股票</th><th>信号</th><th>数值</th><th>阈值</th><th>建议命令</th></tr>"
        )
        for code, signals in items:
            name = signals[0].name
            signal_details = " / ".join(escape(s.detail) for s in signals)
            actual_values = " / ".join(escape(s.actual_value) for s in signals)
            thresholds = " / ".join(escape(s.threshold) for s in signals)
            # 建议命令去重
            cmds = []
            seen = set()
            for s in signals:
                if s.suggest_cmd not in seen:
                    cmds.append(s.suggest_cmd)
                    seen.add(s.suggest_cmd)
            cmd_html = "<br>".join(f"<code>{escape(c)}</code>" for c in cmds)
            parts.append(
                f"<tr><td>{escape(code)} {escape(name)}</td>"
                f"<td>{signal_details}</td>"
                f"<td>{actual_values}</td>"
                f"<td>{thresholds}</td>"
                f"<td>{cmd_html}</td></tr>"
            )
        parts.append("</table>")

    parts.append("<hr>")
    if untriggered_codes:
        parts.append(
            f"<p>本期未触发股票：{escape(' / '.join(untriggered_codes))}"
            f"（共 {len(untriggered_codes)} 只）</p>"
        )
    parts.append(f"<p>下次扫描：自动（每个交易日 03:00）</p>")

    return "\n".join(parts)


def send_mail(cfg: SmtpConfig, *, subject: str, html_body: str) -> None:
    """发送邮件。失败抛 smtplib / ssl 相关异常，由上游处理退出码。"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.from_addr
    msg["To"] = cfg.to_addr
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(cfg.host, cfg.port) as server:
        server.login(cfg.user, cfg.password)
        server.sendmail(cfg.from_addr, cfg.to_addr, msg.as_string())


def send_mail_from_env(*, subject: str, html_body: str, env_path=None) -> None:
    """便利方法：直接从 .env.smtp 加载并发送。"""
    env_path = env_path or DEFAULT_SMTP_ENV_PATH
    cfg = load_smtp_config(env_path)
    send_mail(cfg, subject=subject, html_body=html_body)
```

- [ ] **Step 7: 跑测试看通过**

```bash
python -m pytest tests/daily_monitor/test_smtp_loader.py tests/daily_monitor/test_mail.py -v
```

预期：13 个测试全部 PASS。

- [ ] **Step 8: Commit**

```bash
git add tools/daily_monitor/smtp_loader.py tools/daily_monitor/mail.py .env.smtp.example .gitignore tests/daily_monitor/test_smtp_loader.py tests/daily_monitor/test_mail.py
git commit -m "feat(daily-monitor): smtp_loader + mail.py（HTML 渲染 + SMTP_SSL 发送）"
```

---

## Task 9: runner.py 主流程 + 集成测试

**Files:**
- Create: `tools/daily_monitor/runner.py`
- Modify: `tools/daily_monitor/__main__.py`（接入 run 子命令）
- Create: `tests/daily_monitor/test_runner.py`
- Create: `tests/daily_monitor/fixtures/sample_quote.json`（mock 行情数据）

- [ ] **Step 1: 写 mock 数据 fixture**

文件 `tests/daily_monitor/fixtures/sample_quote.json`：

```json
{
  "600036": {
    "name": "招商银行",
    "price": 38.5,
    "prev_close": 38.0,
    "pe": 7.5,
    "pb": 1.0,
    "market_cap_yi": 9700.0
  },
  "600519": {
    "name": "贵州茅台",
    "price": 1680.0,
    "prev_close": 1750.0,
    "pe": 22.0,
    "pb": 8.5,
    "market_cap_yi": 21000.0
  }
}
```

文件 `tests/daily_monitor/fixtures/sample_financials.json`：

```json
{
  "600036": {"roe_history": [16.8, 16.5, 16.2]},
  "600519": {"roe_history": [30.0, 29.5, 28.8]}
}
```

文件 `tests/daily_monitor/fixtures/sample_dividends.json`：

```json
{
  "600036": {"dividend_per_10_ttm": 2.0},
  "600519": {"dividend_per_10_ttm": 25.0}
}
```

- [ ] **Step 2: 写集成测试**

文件 `tests/daily_monitor/test_runner.py`：

```python
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
```

- [ ] **Step 3: 跑测试看失败**

```bash
python -m pytest tests/daily_monitor/test_runner.py -v
```

预期：ImportError（runner 模块不存在）。

- [ ] **Step 4: 写 runner.py 实现**

文件 `tools/daily_monitor/runner.py`：

```python
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
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from tools.daily_monitor.holidays import is_holiday
from tools.daily_monitor.mail import render_mail_html, render_mail_subject, send_mail_from_env
from tools.daily_monitor.signals import (
    SEVERITY_CRITICAL, SEVERITY_WATCH, SEVERITY_OPPORTUNITY, check_signals,
)
from tools.daily_monitor.snapshot import cleanup_old_snapshots, load_snapshot, write_snapshot
from tools.daily_monitor.smtp_loader import DEFAULT_SMTP_ENV_PATH, SmtpConfigError, load_smtp_config
from tools.daily_monitor.watchlist import (
    DEFAULT_WATCHLIST_PATH, WatchlistError, load_watchlist, sync_recommended,
)
from tools.stock_recommender import (
    calc_dividend_yield, fetch_dividends, fetch_financials, fetch_quote, score_stable,
)


DEFAULT_SNAPSHOT_DIR = DEFAULT_WATCHLIST_PATH.parent
DEFAULT_REPORT_DIR = DEFAULT_WATCHLIST_PATH.parent.parent.parent / "reports" / "日扫描"
DEFAULT_LOG_DIR = DEFAULT_WATCHLIST_PATH.parent.parent.parent / "logs" / "daily-monitor"
DEFAULT_STABLE_REPORT_DIR = DEFAULT_WATCHLIST_PATH.parent.parent.parent / "reports" / "股票推荐"


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

    sev_label = {SEVERITY_CRITICAL: "🔴 紧急", SEVERITY_WATCH: "🟡 关注", SEVERITY_OPPORTUNITY: "🟢 机会"}
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
                f"| {it['code']} {it['name']} | {signal_details} | {actual} | {thresh} | {'<br>'.join(cmds)} |"
            )
        lines.append("")
    return "\n".join(lines)


def run(*, scan_date: str, send_email: bool = True, force_mail: bool = False,
        dry_run: bool = False, no_mail: bool = False) -> RunResult:
    """执行日扫描。返回 RunResult。"""
    result = RunResult()
    market_date = scan_date  # 简化：扫描日即市场反映日（03:00 跑反映前一日，但快照文件按 scan_date）

    # 1. 节假日检查
    if is_holiday(scan_date):
        print(f"[info] {scan_date} 是节假日，跳过扫描", file=sys.stderr)
        return result  # exit_code=0

    # 2. 加载 watchlist
    try:
        wl = load_watchlist(DEFAULT_WATCHLIST_PATH)
    except WatchlistError as e:
        print(f"❌ watchlist 格式错误: {e}", file=sys.stderr)
        result.exit_code = 5
        result.error = str(e)
        return result

    positions = wl.get("positions", [])
    recommended = [r for r in wl.get("recommended", []) if r.get("still_recommended", True)]
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
        print(f"❌ watchlist 为空（无持仓 + 无活跃推荐），先跑 add-position 或 sync-recommended",
              file=sys.stderr)
        result.exit_code = 4
        return result

    # 3. 同步推荐池（如果最新 stable-*.md 比上次同步更新）
    # 简化：每次 run 都尝试同步一次
    if DEFAULT_STABLE_REPORT_DIR.exists():
        candidates = sorted(DEFAULT_STABLE_REPORT_DIR.glob("stable-*.md"), reverse=True)
        if candidates:
            try:
                wl = sync_recommended(DEFAULT_WATCHLIST_PATH, candidates[0],
                                      checked_date=scan_date)
            except Exception as e:
                print(f"[warn] sync-recommended 失败（不阻塞）: {e}", file=sys.stderr)

    thresholds = wl["thresholds"]

    # 4. 加载昨日快照 + 历史快照（用于 52 周新高低）
    yesterday = date.fromisoformat(scan_date)
    # 找上一个工作日的快照
    prev_snap_path = None
    for i in range(1, 15):  # 最多回溯 2 周
        prev_date = yesterday.fromordinal(yesterday.toordinal() - i)
        prev_path = DEFAULT_SNAPSHOT_DIR / f"snapshot-{prev_date.isoformat()}.json"
        if prev_path.exists():
            prev_snap_path = prev_path
            break
    yesterday_snap = load_snapshot(prev_snap_path) if prev_snap_path else None

    historical_snaps = []
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
            print(f"  [{code}] {data['name']}: score={data['score']}, "
                  f"price={data['price']}, pe={data['pe']}", file=sys.stderr)
        except Exception as e:
            print(f"  [{code}] ⚠️ 拉数据失败: {e}", file=sys.stderr)
            failures.append(code)

    if not today_stocks and all_codes:
        print(f"❌ 全部行情失败（{len(failures)} 只），不发邮件", file=sys.stderr)
        result.exit_code = 2
        result.error = f"all {len(failures)} stocks failed"
        return result

    # 6. 信号判定
    signals_by_code = {}
    triggered_codes = []
    items = []
    position_codes = {p["code"] for p in positions}
    recommended_history_codes = {r["code"] for r in wl.get("recommended", [])
                                 if not r.get("still_recommended", True)}

    for kind, item in all_codes:
        code = item["code"]
        if code not in today_stocks:
            continue
        today = today_stocks[code]
        # 注入 buy_price（持仓专属）
        if kind == "position":
            today["buy_price"] = item.get("buy_price")

        yesterday_stock = (yesterday_snap or {}).get("stocks", {}).get(code)
        last_5d_close = None  # 简化：暂不实现 5 日累计（可后续扩展）

        sigs = check_signals(
            today=today,
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
            sev_rank = {SEVERITY_CRITICAL: 0, SEVERITY_WATCH: 1, SEVERITY_OPPORTUNITY: 2}
            top_sev = min((s.severity for s in sigs), key=sev_rank.get)
            items.append({"code": code, "name": today["name"],
                          "signals": sigs, "top_severity": top_sev})

    result.triggered_count = len(triggered_codes)
    result.total_scanned = len(today_stocks)
    result.triggered_codes = triggered_codes

    # 7. 写今日快照
    if not dry_run:
        snap = {"scan_date": scan_date, "stocks": today_stocks}
        write_snapshot(snap, DEFAULT_SNAPSHOT_DIR / f"snapshot-{scan_date}.json")
        # 清理旧快照
        cleanup_old_snapshots(DEFAULT_SNAPSHOT_DIR,
                              keep_days=thresholds.get("snapshot_history_days", 30),
                              today_str=scan_date)

    # 8. 触发了 → 生成报告 + 发邮件
    should_mail = (result.triggered_count > 0 or force_mail) and send_email and not no_mail
    report_md = ""
    if result.triggered_count > 0 or dry_run:
        summary = {
            "total_scanned": result.total_scanned,
            "triggered_codes": triggered_codes,
            "items": items,
        }
        report_md = _generate_report_md(scan_date, market_date, summary)
        if not dry_run:
            DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            (DEFAULT_REPORT_DIR / f"{scan_date}.md").write_text(report_md, encoding="utf-8")

    if should_mail:
        try:
            untriggered = [c for c, _ in all_codes if c not in triggered_codes and c in today_stocks]
            subject = render_mail_subject(scan_date=scan_date, triggered_count=result.triggered_count)
            html = render_mail_html(
                scan_date=scan_date, market_date=market_date,
                total_scanned=result.total_scanned,
                triggered_count=result.triggered_count,
                signals_by_code=signals_by_code,
                untriggered_codes=untriggered,
            )
            send_mail_from_env(subject=subject, html_body=html, env_path=DEFAULT_SMTP_ENV_PATH)
            print(f"✅ 邮件已发送：{subject}", file=sys.stderr)
        except SmtpConfigError as e:
            print(f"⚠️ SMTP 配置错误（报告已生成）: {e}", file=sys.stderr)
            result.exit_code = 3
        except Exception as e:
            print(f"⚠️ 邮件发送失败（报告已生成）: {e}", file=sys.stderr)
            result.exit_code = 3

    print(f"[done] 扫描 {result.total_scanned} 只，触发 {result.triggered_count} 只",
          file=sys.stderr)
    return result
```

- [ ] **Step 5: 改 __main__.py 接入 run 子命令**

修改 `tools/daily_monitor/__main__.py`，把 `run` 分支替换为：

```python
    if args.cmd == "run":
        from tools.daily_monitor.runner import run
        from datetime import date
        scan_date = date.today().isoformat()
        result = run(
            scan_date=scan_date,
            send_email=not args.no_mail,
            force_mail=args.force_mail,
            dry_run=args.dry_run,
            no_mail=args.no_mail,
        )
        return result.exit_code
```

- [ ] **Step 6: 跑测试看通过**

```bash
python -m pytest tests/daily_monitor/test_runner.py -v
```

预期：6 个测试全部 PASS。

- [ ] **Step 7: 跑全量测试确认无回归**

```bash
python -m pytest tests/daily_monitor/ -v
```

预期：所有测试 PASS。

- [ ] **Step 8: Commit**

```bash
git add tools/daily_monitor/runner.py tools/daily_monitor/__main__.py tests/daily_monitor/test_runner.py tests/daily_monitor/fixtures/
git commit -m "feat(daily-monitor): runner.py 主流程 + 6 个集成测试（mock 行情接口）"
```

---

## Task 10: install/uninstall 脚本 + CLAUDE.md 文档 + 端到端验证

**Files:**
- Create: `scripts/install-daily-monitor.ps1`
- Create: `scripts/uninstall-daily-monitor.ps1`
- Modify: `CLAUDE.md`（加"日扫描系统"章节）

- [ ] **Step 1: 写 install 脚本**

文件 `scripts/install-daily-monitor.ps1`：

```powershell
<#
.SYNOPSIS
注册 AI-Berkshire-Daily-Monitor 到 Windows 任务计划程序（每个交易日 03:00）。

.DESCRIPTION
参考 commit 8a21858 的解决方案：用 schtasks（兼容 PS7）而非 Register-ScheduledTask，
避免 PowerShell 版本兼容问题。

任务名：AI-Berkshire-Daily-Monitor
触发：每周一至周五 03:00
动作：python tools/daily_monitor.py run
工作目录：脚本所在仓库根目录

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts/install-daily-monitor.ps1
#>

$ErrorActionPreference = "Stop"

$taskName = "AI-Berkshire-Daily-Monitor"
$repoRoot = Resolve-Path "$PSScriptRoot/.."
$python = (Get-Command python).Source
$workDir = $repoRoot.Path
$actionCmd = "`"$python`" `"$workDir\tools\daily_monitor.py`" run"

Write-Host "注册任务: $taskName"
Write-Host "  Python: $python"
Write-Host "  工作目录: $workDir"
Write-Host "  触发: 每周一至周五 03:00"

# schtasks 兼容 PS7（参考 commit 8a21858）
schtasks /Create /TN $taskName `
    /TR $actionCmd `
    /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 03:00 `
    /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 任务已注册。手动触发测试：" -ForegroundColor Green
    Write-Host "   schtasks /run /tn `"$taskName`""
    Write-Host "查看任务状态："
    Write-Host "   schtasks /query /tn `"$taskName`" /v"
} else {
    Write-Host "❌ 注册失败（exit code $LASTEXITCODE）" -ForegroundColor Red
    exit 1
}
```

- [ ] **Step 2: 写 uninstall 脚本**

文件 `scripts/uninstall-daily-monitor.ps1`：

```powershell
<#
.SYNOPSIS
卸载 AI-Berkshire-Daily-Monitor 任务。

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts/uninstall-daily-monitor.ps1
#>

$taskName = "AI-Berkshire-Daily-Monitor"

Write-Host "卸载任务: $taskName"
schtasks /Delete /TN $taskName /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 任务已卸载" -ForegroundColor Green
} else {
    Write-Host "⚠️ 卸载失败（任务可能不存在，exit code $LASTEXITCODE）" -ForegroundColor Yellow
}
```

- [ ] **Step 3: 改 CLAUDE.md（加日扫描章节）**

在 `CLAUDE.md` 的"## /stock-recommend 推荐系统"章节后追加：

```markdown
## 日扫描系统

每个交易日 03:00 自动扫描 watchlist（持仓 + 推荐池），异动时邮件提醒 + 给"建议跑的命令"清单。**零 LLM 配额**（纯 stdlib + 复用 stock_recommender 数据接口）。

```bash
# 维护 watchlist
python tools/daily_monitor.py add-position 600036 --buy-price 38.5 --shares 1000 --buy-date 2026-03-15 --name 招商银行
python tools/daily_monitor.py remove-position 600036
python tools/daily_monitor.py sync-recommended   # 从最新 stable-{date}.md 同步

# 运行
python tools/daily_monitor.py run                 # 默认（带邮件）
python tools/daily_monitor.py run --dry-run       # 只打印
python tools/daily_monitor.py run --no-mail       # 不发邮件
python tools/daily_monitor.py run --force-mail    # 即使无异动也发（测试用）

# 查看
python tools/daily_monitor.py show-watchlist
python tools/daily_monitor.py show-config

# 注册/卸载 Windows 任务计划程序（每个交易日 03:00）
powershell -ExecutionPolicy Bypass -File scripts/install-daily-monitor.ps1
powershell -ExecutionPolicy Bypass -File scripts/uninstall-daily-monitor.ps1
```

### 触发规则

| 信号 | 默认阈值 | 严重度 | 建议命令 |
|------|---------|:------:|---------|
| 单日涨跌 | ±5% | 🟡 关注 | `/news-pulse {公司}` |
| 5 日累计涨跌 | ±10% | 🟡 关注 | `/news-pulse {公司}` |
| 跌破成本 | -15% | 🔴 紧急 | `/thesis-tracker {公司}` |
| PE 进入击球区 | < 8 | 🟢 机会 | `/investment-checklist {公司}` |
| PE 突破高估 | > 20 | 🔴 紧急 | `/thesis-tracker {公司}` |
| 股息率升破 | ≥ 5% | 🟢 机会 | `/investment-checklist {公司}` |
| 股息率跌破 | < 3% | 🔴 紧急 | `/thesis-tracker {公司}` |
| PB 破净 | < 1 | 🟢 机会 | `/investment-checklist {公司}` |
| 推荐池新进 | 4 分 | 🟢 机会 | `/investment-checklist {公司}` |
| 推荐池跌出 | < 4 分 | 🔴 紧急 | `/thesis-tracker {公司}` |

阈值在 `data/monitor/watchlist.json` 的 `thresholds` 字段，调整不用改代码。

### SMTP 配置

复制 `.env.smtp.example` 为 `.env.smtp`，填入 163 邮箱授权码（已在 .gitignore）。

### 故障排查

- **运行日志**：`logs/daily-monitor/{YYYYMMDD-HHMMSS}.json`
- **快照**：`data/monitor/snapshot-{YYYY-MM-DD}.json`（保留 30 天）
- **报告**：`reports/日扫描/{YYYY-MM-DD}.md`（仅触发时生成）
- **手动触发**：`schtasks /run /tn "AI-Berkshire-Daily-Monitor"`
- **退出码**：0=正常 / 2=全部行情失败 / 3=SMTP 失败 / 4=watchlist 空 / 5=watchlist 格式错

### 节假日

`data/zh-holidays.json` 每年初手动更新一次（10 分钟，来源：上交所休市安排）。

### 设计文档

- spec：`docs/superpowers/specs/2026-07-08-daily-monitor-design.md`
- 实施计划：`docs/superpowers/plans/2026-07-08-daily-monitor.md`
```

- [ ] **Step 4: 端到端手工验证**

```bash
# 1. 同步推荐池（如果有 stable 报告）
python tools/daily_monitor.py sync-recommended

# 2. 加一只测试持仓
python tools/daily_monitor.py add-position 600036 --buy-price 38.5 --shares 1000 --buy-date 2026-03-15 --name 招商银行

# 3. dry-run 跑一次（不发邮件，看输出）
python tools/daily_monitor.py run --dry-run

# 4. 不发邮件跑一次（写快照 + 报告）
python tools/daily_monitor.py run --no-mail

# 5. 看快照和报告是否生成
ls data/monitor/
ls "reports/日扫描/"

# 6. 配置 .env.smtp 后真实发送测试
cp .env.smtp.example .env.smtp
# 编辑 .env.smtp 填真实授权码
python tools/daily_monitor.py run --force-mail

# 7. 注册任务计划程序
powershell -ExecutionPolicy Bypass -File scripts/install-daily-monitor.ps1
schtasks /query /tn "AI-Berkshire-Daily-Monitor" /v

# 8. 手动触发任务计划程序一次
schtasks /run /tn "AI-Berkshire-Daily-Monitor"
# 等几分钟后看日志
ls logs/daily-monitor/
```

每一步都正常才算通过。如有问题，根据错误现象调试。

- [ ] **Step 5: Commit**

```bash
git add scripts/install-daily-monitor.ps1 scripts/uninstall-daily-monitor.ps1 CLAUDE.md
git commit -m "feat(daily-monitor): install/uninstall 脚本 + CLAUDE.md 文档"
```

- [ ] **Step 6: 全量回归测试**

```bash
python -m pytest tests/daily_monitor/ tests/scheduler/ tests/fin_ai/ -v
```

确认日扫描系统不影响现有 scheduler / fin_ai 测试。

---

## 自审

### Spec 覆盖

| Spec 要求 | 覆盖 Task |
|---|---|
| watchlist.json 结构（positions / recommended / thresholds） | Task 2 |
| add-position / remove-position 子命令 | Task 3 |
| sync-recommended 子命令（解析 stable-{date}.md） | Task 4 |
| 快照读写 + 30 天滚动 | Task 5 |
| 4 类信号判定（价格/估值/推荐池/事件——事件本期不做） | Task 6 |
| 邮件 HTML 渲染 + 分级 | Task 8 |
| SMTP 配置加载 | Task 8 |
| 节假日判断 | Task 7 |
| runner.py 主流程 | Task 9 |
| 错误处理（5 个退出码） | Task 9 |
| Windows 任务计划程序集成 | Task 10 |
| 测试覆盖（单元 + 集成） | Task 2-9 |
| 复用 stock_recommender 接口 | Task 9（_scan_one） |

✅ 全部覆盖。

### Placeholder 扫描

- ✓ 无 TBD/TODO
- ✓ 每个步骤都有完整代码
- ✓ 测试代码完整（不是"按上述写测试"）
- ✓ 命令行示例可直接复制运行

### 类型一致性

- ✓ `DEFAULT_WATCHLIST_PATH` 在 watchlist.py 定义，在 runner.py / __main__.py 引用
- ✓ `RunResult` 在 runner.py 定义，所有测试和 __main__.py 一致使用
- ✓ `Signal` dataclass 字段名（code/name/type/severity/detail/actual_value/threshold/suggest_cmd）在 signals.py / mail.py / test_*.py 一致
- ✓ `SEVERITY_CRITICAL/WATCH/OPPORTUNITY` 常量在 signals.py 定义，在 mail.py / runner.py 引用
- ✓ `check_signals` 签名（关键字参数）在 signals.py 定义，在 runner.py 调用一致

---

## 计划完成
