""".env.smtp 解析。

格式：KEY=VALUE 每行一对，# 开头注释，空行忽略。
必需字段：SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / SMTP_FROM / SMTP_TO

不引入 python-dotenv，避免新增依赖。
"""

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
