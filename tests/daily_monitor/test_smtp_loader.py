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
