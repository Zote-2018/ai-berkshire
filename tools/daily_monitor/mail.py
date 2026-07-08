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
