# 日扫描系统设计（2026-07-08）

## 背景

`stock_recommender.py` 是**一次性快照**推荐——出报告就完了。`thesis-tracker` / `news-pulse` / `portfolio-review` 都要**手动触发**——用户得先看到股价异动才能想起来跑。调度 Pipeline（周/月频）当前因 headless 卡死**已卸载待重装**（见 `memory/project_next_pipeline.md`）。

核心痛点：**推荐和持仓之间缺一个"持续监控 + 主动提醒"的中间层**。用户想：

- 让系统每天扫一次 watchlist（持仓 + 推荐池），不依赖手动记忆
- 异动了通过邮件主动 push，不用自己想起来看报告
- 邮件里直接给出"建议跑的命令"（半自动），用户决定是否升级到深度 skill

## 用户决策（2026-07-08）

| 决策点 | 选定方案 | 理由 |
|---|---|---|
| 监控对象 | **持仓 + 推荐池** | 既能管已买入的（清仓/加仓），又能盯推荐池里没买的（"现在跌出机会了"） |
| 扫描频率 | **日频扫描 + 异动升级** | 平日只做免费数据扫描，异动了才升级到深度 skill；不烧套餐配额 |
| 触发信号 | **价格 + 估值 + 推荐池变动**（事件信号本期不做） | 4 类全要，事件信号靠手动 `news-pulse` 补 |
| 提醒渠道 | **163 邮件 SMTP** | 用户已有 163 邮箱，国内最稳；零外部依赖（stdlib smtplib） |
| 自动化程度 | **半自动：提醒 + 给命令** | 邮件含"建议跑的命令"清单，配额经济、控制感强 |
| 持仓维护 | **手动维护 `watchlist.json`** | 子命令 `add-position` / `remove-position` 增删；`portfolio-latest.md` 格式不固定，解析不可靠 |
| 邮件频率 | **仅异动时发 + 汇总一封** | 避免每天打扰；多只异动合并在当日报告里 |
| 扫描时间 | **每个交易日 03:00** | 用户偏好"凌晨跑、次日操作"；避开白天配额高峰；与现有调度任务（Portfolio-Weekly / Industry-Monthly）时间一致 |
| 节假日识别 | **手动维护 `data/zh-holidays.json`** | 个人项目够用，避免新增 API 依赖 |
| 阈值 | **默认值**（价格 ±5%/±10% / PE 8-20 / 股息率 5%/3% / 止损 -15%） | 后续按实际喷砂调整 `watchlist.json` 即可，不用动代码 |

## 备选方案对比

### A. 纯 Python 脚本（无 LLM）✅

| 维度 | 评价 |
|---|---|
| 配额压力 | **0**（纯 stdlib + 腾讯行情/东财，免费） |
| 实施复杂度 | **低**（单文件 ~500 行） |
| 跑得快 | 是（10 秒级） |
| 事件信号 | **缺失**（价格/估值变化可推断"有事"，但不知道具体是什么事） |
| 依赖 | 零（不依赖 scheduler / claude headless） |
| **判断** | **MVP 首选** |

### B. 复用 scheduler 框架 + claude headless 扫事件

| 维度 | 评价 |
|---|---|
| 配额压力 | 每日 1-2 次套餐配额 |
| 实施复杂度 | 中（写 `/daily-monitor` skill + runner.py 集成） |
| 事件信号 | 覆盖最全（LLM 解读 tavily 抓的新闻） |
| 风险 | scheduler 之前 headless 卡死过（runner.py 已加固，但仍是风险点） |
| **判断** | 不推荐（半自动模式下扫描层不需要 LLM） |

### C. 脚本扫价格/估值 + fin_ai 补事件

| 维度 | 评价 |
|---|---|
| 配额压力 | fin_ai 80/天（watchlist 20 只 × 1 次/天 = 80，刚够） |
| 实施复杂度 | 中（在 A 基础上加 fin_ai 调用） |
| 事件信号 | 中等（fin_ai 解读事件，但不写完整研报） |
| **判断** | A 跑通后的渐进升级路径，本期不做 |

## 架构与数据流

### 文件布局

```
tools/daily_monitor.py                # 单文件 CLI，主逻辑
data/monitor/
  ├── watchlist.json                  # 持仓 + 推荐池 + 阈值配置（手动 + 自动同步混合维护）
  └── snapshot-{YYYYMMDD}.json        # 每日快照（自动生成，保留 30 天）
data/zh-holidays.json                 # 中国节假日列表（每年初手动维护）
reports/日扫描/
  └── {YYYYMMDD}.md                   # 触发时生成报告（日期=扫描日，反映上一交易日市场）
scripts/install-daily-monitor.ps1     # Windows 任务计划程序注册脚本
scripts/uninstall-daily-monitor.ps1   # 卸载脚本
.env.smtp                             # SMTP 配置（gitignore）
tests/daily_monitor/                  # 单元 + 集成测试
```

### 数据流（每个交易日 03:00）

```
[输入]
  data/monitor/watchlist.json
  data/monitor/snapshot-{上一交易日}.json    ← 昨日快照（首次为空）

        ↓
[扫描层]  tools/daily_monitor.py run
  1. 节假日检查（zh-holidays.json）→ 命中则退出码 0，不报警
  2. 加载 watchlist（positions + recommended）
  3. 同步推荐池：解析最新 stable-{date}.md，新进/退出标到 recommended
  4. 并行拉腾讯行情 + 东财财务/分红
  5. 重跑 stock_recommender.score_stable 4 维打分
  6. 对比昨日快照 + 检查绝对阈值，判断 4 类信号是否触发
        ↓
[分支]
  ├── 触发了 → 生成 reports/日扫描/{date}.md
  │            → SMTP 发汇总邮件（按 [紧急]/[关注]/[机会] 分节）
  └── 没触发 → 跳过邮件，只写今日快照

        ↓
[输出]
  data/monitor/snapshot-{今日}.json   ← 今日快照（保留 30 天滚动）
  reports/日扫描/{date}.md（触发时）
  邮件（触发时）
```

## watchlist.json 结构

```json
{
  "version": 1,
  "thresholds": {
    "price_change_daily_pct": 5.0,
    "price_change_5d_pct": 10.0,
    "cost_drawdown_pct": 15.0,
    "pe_undervalued": 8,
    "pe_overvalued": 20,
    "dividend_yield_high": 5.0,
    "dividend_yield_low": 3.0,
    "snapshot_history_days": 30
  },
  "positions": [
    {
      "code": "600519",
      "name": "贵州茅台",
      "buy_price": 1680.0,
      "shares": 100,
      "buy_date": "2026-03-15",
      "added_at": "2026-03-15"
    }
  ],
  "recommended": [
    {
      "code": "600036",
      "name": "招商银行",
      "first_recommended_date": "2026-07-04",
      "score_at_recommend": 4,
      "still_recommended": true,
      "last_checked_date": "2026-07-08"
    }
  ]
}
```

**维护规则**：
- `positions`：仅由 `add-position` / `remove-position` 子命令修改
- `recommended`：每次 `run` 自动同步——新进推荐追加，跌出推荐的标 `still_recommended: false` 但**不删除**（保留观察历史）
- `thresholds`：手动编辑，所有阈值集中一处

## 触发规则

### 4 类信号判定

| 信号类型 | 触发条件 | 默认阈值 | 严重度 | 触发后建议命令 |
|---|---|---|:---:|---|
| **价格异动** | 单日涨跌幅 ≥ X% | ±5% | 🟡 关注 | `/news-pulse {公司} {涨/跌}{X}% 1天` |
| | 5 日累计涨跌幅 ≥ Y% | ±10% | 🟡 关注 | `/news-pulse {公司} {涨/跌}{Y}% 5天` |
| | 跌破买入成本 -Z%（仅持仓） | -15% | 🔴 紧急 | `/thesis-tracker {公司}` |
| | 创 52 周新低（需 ≥ 200 个交易日快照积累，约 9 个月） | — | 🔴 紧急 | `/thesis-tracker {公司}` |
| | 创 52 周新高（同上） | — | 🟢 机会 | `/thesis-tracker {公司}` |
| **估值变化** | PE 进入击球区 | < 8 | 🟢 机会 | `/investment-checklist {公司}` |
| | PE 突破高估区 | > 20 | 🔴 紧急 | `/thesis-tracker {公司}` |
| | 股息率升破 X%（推荐池机会） | > 5% | 🟢 机会 | `/investment-checklist {公司}` |
| | 股息率跌破 Y%（持仓警示） | < 3% | 🔴 紧急 | `/thesis-tracker {公司}` |
| | PB 破净 | < 1 | 🟢 机会 | `/investment-checklist {公司}` |
| **推荐池变动** | 新进 4 分强推荐 | — | 🟢 机会 | `/investment-checklist {公司}` |
| | 4 分 → 跌出强推荐 | — | 🔴 紧急 | `/thesis-tracker {公司}` |
| | 曾推荐 → 跌出 → 重新进入 | — | 🟢 机会 | `/investment-checklist {公司}` |

### 同股票多信号合并

一只股票一天只产生一条 watchlist 项，所有触发信号合并在那一节的"信号"列展示（例如：`单日跌 5.2% / PE 进入击球区`），建议命令去重后列出。

### 首次运行特殊处理

`data/monitor/snapshot-{昨天}.json` 不存在时：
- **跳过**所有对比类信号（价格异动、推荐池变动、52 周新高低）
- **仍检查**绝对阈值类信号（PE 击球区/高估、股息率临界、PB 破净）
- 在报告顶部标注"首次运行，对比类信号不可用"

## 邮件格式

### 标题

- 触发：`[日扫描] 2026-07-08 共 3 只异动`
- 无触发：默认不发，`--force-mail` 时发 `[日扫描] 2026-07-08 无异动`

> 日期是**扫描日**（03:00 跑的当天），内容反映**上一交易日**（昨天）的市场。

### 正文（HTML）

```html
<h2>📊 日扫描 — 2026-07-08</h2>
<p>扫描 watchlist 共 15 只（持仓 5 + 推荐池 10），<b>3 只触发信号</b>。
反映 2026-07-07（周一）市场。</p>

<h3>🔴 紧急（1）</h3>
<table border="1" cellpadding="6">
  <tr><th>股票</th><th>信号</th><th>数值</th><th>阈值</th><th>建议命令</th></tr>
  <tr>
    <td>600036 招商银行<br><small>持仓 1000 股 @38.5</small></td>
    <td>跌破成本</td>
    <td>-15.3%</td>
    <td>-15%</td>
    <td><code>/thesis-tracker 招商银行</code></td>
  </tr>
</table>

<h3>🟡 关注（1）</h3>
<table>...600519 茅台 单日跌 5.2% ...</table>

<h3>🟢 机会（1）</h3>
<table>...601318 中国平安 PE 7.8 进入击球区 ...</table>

<hr>
<p>完整报告：<code>reports/日扫描/2026-07-08.md</code></p>
<p>本期未触发股票：600276 恒瑞医药 / 000858 五粮液 / ...（共 12 只）</p>
<p>下次扫描：2026-07-09 03:00</p>
```

### SMTP 配置

```
# .env.smtp （加入 .gitignore）
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=xxx@163.com
SMTP_PASS=授权码（不是登录密码，163 邮箱后台开 SMTP 生成）
SMTP_FROM=xxx@163.com
SMTP_TO=yyy@163.com
```

加载方式：`python-dotenv` 不引入，手写 8 行 stdlib 解析（避免新增依赖）。

## CLI 子命令

```bash
# === 维护 ===
python tools/daily_monitor.py add-position 600036 \
    --buy-price 38.5 --shares 1000 --buy-date 2026-03-15

python tools/daily_monitor.py remove-position 600036

python tools/daily_monitor.py sync-recommended
    # 解析最新 reports/股票推荐/stable-{date}.md，更新 watchlist.json 的 recommended 字段

# === 运行 ===
python tools/daily_monitor.py run                 # 默认（带邮件）
python tools/daily_monitor.py run --dry-run       # 只打印不发送，不写快照
python tools/daily_monitor.py run --no-mail       # 跑但不发邮件（先看报告）
python tools/daily_monitor.py run --force-mail    # 即使无异动也发（测试用）

# === 查看 ===
python tools/daily_monitor.py show-watchlist
python tools/daily_monitor.py show-snapshot --date 2026-07-07
python tools/daily_monitor.py show-config
```

## 错误处理

| 故障场景 | 处理方式 | 退出码 |
|---|---|:---:|
| 节假日 | 跳过，stderr 打印 `[info] 今日节假日，跳过扫描` | 0 |
| 单只股票行情失败 | 跳过该股票，stderr warn，标 `data_unavailable`，不阻塞 | 0（含部分失败） |
| 全部行情失败（网络故障） | **不发邮件**（避免误报"全市场无异动"），stderr 报错 | 2 |
| SMTP 失败 | 报告照常生成到 `reports/日扫描/`，stderr 报错 | 3 |
| watchlist.json 不存在 | 提示先跑 `add-position` 或 `sync-recommended` | 4 |
| watchlist.json 格式错误 | stderr 报具体行号，不跑 | 5 |
| 昨日快照不存在（首次运行） | 不报错，跳过对比类信号，仍检查绝对阈值 | 0 |
| `.env.smtp` 不存在 | 触发邮件时 stderr 报错，但报告照常生成 | 3 |

**核心原则**：单只股票失败 ≠ 整体失败。金融系统不能因为一个数据点失败就停摆。

## Windows 任务计划程序集成

### 注册脚本（参考现有 `install-windows-tasks.ps1` 风格）

```powershell
# scripts/install-daily-monitor.ps1
$taskName = "AI-Berkshire-Daily-Monitor"
$workDir = "C:\workspace\ai-berkshire"

# 用 schtasks（兼容 PS7，参考 commit 8a21858 的解决方案）
schtasks /Create /TN $taskName `
    /TR "python $workDir/tools/daily_monitor.py run" `
    /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 03:00 `
    /F
```

### 节假日列表（手动维护）

```json
// data/zh-holidays.json
{
  "2026": [
    "2026-01-01", "2026-02-16", "2026-02-17", "...",
    "2026-05-01", "2026-10-01", "..."
  ]
}
```

每年元旦后花 10 分钟更新一次（来源：证监会/上交所发布的休市安排）。

### 故障排查

- **日志位置**：`logs/daily-monitor/{YYYYMMDD-HHMMSS}.json`（参考 `tools/scheduler/runner.py` 的日志格式）
- **手动触发**：`schtasks /run /tn "AI-Berkshire-Daily-Monitor"`
- **查看任务**：`schtasks /query /tn "AI-Berkshire-Daily-Monitor" /v`

## 测试策略

参考现有 `tests/scheduler/` 和 `tests/fin_ai/` 的风格。

### 单元测试（必跑）

| 测试目标 | 覆盖点 |
|---|---|
| `signals.py` 信号判定 | 4 类信号的阈值比较（边界值、刚触发/差一点） |
| `snapshot.py` 快照 diff | 昨日 vs 今日对比逻辑、首次运行处理 |
| `watchlist.py` CRUD | `add-position` / `remove-position` / `sync-recommended` 数据正确性 |
| `mail.py` 邮件生成 | HTML 渲染、分级分组、多信号合并 |
| `smtp_loader.py` 配置加载 | `.env.smtp` 解析（含缺字段、格式错误） |
| `holidays.py` 节假日 | 命中/未命中、跨年数据 |

### 集成测试

- mock `fetch_quote` / `fetch_financials` / `fetch_dividends` 的返回值（固定 fixture JSON）→ 跑完整 `run --dry-run` → 断言生成的报告内容 + 邮件 HTML
- 模拟"单只股票行情失败"（让某只股票的 `fetch_quote` 抛异常），断言其他股票仍正常处理
- 模拟"全部行情失败"，断言不发邮件 + 退出码 2

### 不测（手工验证）

- 真实 SMTP 发送（手工跑 `--force-mail` 一次确认）
- 真实腾讯行情（手工跑 `--dry-run` 看抓回的数据）
- 真实 Windows 任务计划程序触发（注册后等 1 天看日志）

## 复用现有代码

直接 `import` 不重造：

- `tools.stock_recommender.fetch_quote`（腾讯行情）
- `tools.stock_recommender.fetch_financials`（东财 ROE）
- `tools.stock_recommender.fetch_dividends`（东财分红）
- `tools.stock_recommender.score_stable`（4 维打分）
- `tools.stock_recommender.calc_dividend_yield`（股息率计算）
- `tools.stock_recommender.load_index_constituents`（指数成分股基线）

`daily_monitor.py` 主要新增逻辑：
- watchlist 管理（CLI + JSON）
- 快照存档与 diff
- 信号判定（4 类）
- 邮件渲染与 SMTP 发送
- 节假日判断

预估代码量：约 500-700 行（单文件 + 1-2 个辅助模块）。

## 不在本期做

| 不做的事 | 留到什么时候 |
|---|---|
| 事件信号（管理层变动、监管政策、竞对动作等） | 后续按方案 C 升级（接 fin_ai），或手动跑 `/news-pulse` |
| 盘中实时提醒 | 配额不允许；保留日频节奏 |
| SMS / Bark / 钉钉机器人推送 | 邮件够用；如需多渠道后续在 `mail.py` 抽象 |
| 自动跑深度 skill（thesis-tracker / news-pulse） | 半自动模式交给用户决策；后续可加 `--auto-escalate` 开关 |
| watchlist 自动从 `portfolio-latest.md` 解析持仓 | 格式不固定，解析脆；用户手动维护更准 |
| 自动同步 `data/zh-holidays.json`（接交易所 API） | 手动维护成本可接受（10 分钟/年） |
| 邮件回执 / 已读追踪 | 过度工程 |
| GitHub Actions 云端备份 | 单机稳定后再考虑 |

## 实施顺序（建议 TDD）

1. `watchlist.py` + CLI 子命令（add/remove/sync/show）
2. `snapshot.py` 快照读写 + diff
3. `signals.py` 4 类信号判定（单元测试密集）
4. `mail.py` 邮件 HTML 渲染
5. `smtp_loader.py` + SMTP 发送
6. `holidays.py` 节假日判断
7. `daily_monitor.py run` 主流程（串起来）
8. `install-daily-monitor.ps1` + 端到端验证

每步都先写测试再写实现（参考 `tests/scheduler/` 已有的 TDD 风格）。
