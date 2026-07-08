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
    """send_mail 调用 smtplib.SMTP_SSL.sendmail，参数正确。

    注意：MIME 标准下中文 Subject 会被 base64 编码（=?utf-8?b?...?=），
    正文也会被 base64 编码，所以走"解析 MIME 结构 + decode_header"而非"明文 in"。
    """
    from email import message_from_string
    from email.header import decode_header, make_header

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
        # 解析 MIME 结构，确认标题和正文正确（自动解码 base64 头部）
        msg = message_from_string(args[2])
        assert str(make_header(decode_header(msg["Subject"]))) == "测试标题"
        assert msg["From"] == "me@163.com"
        assert msg["To"] == "you@163.com"
        html_part = msg.get_payload()[0]
        assert html_part.get_payload(decode=True).decode("utf-8") == "<html>测试</html>"
