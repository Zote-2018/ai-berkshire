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
    """不在列表中的工作日返回 False（2026-05-02 是周六会被周末判定命中，故改用 05-06 周三）。"""
    path = tmp_path / "zh-holidays.json"
    path.write_text('{"2026": ["2026-05-01"]}', encoding="utf-8")
    assert is_holiday("2026-05-06", holidays_path=path) is False


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
