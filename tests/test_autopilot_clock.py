from datetime import datetime, date, timezone
from tools.autopilot_clock import is_market_open, brain_model_for, brain_label

# Mon Jul 6 2026, 14:00 UTC == 10:00 ET (EDT) -> open
OPEN_UTC = datetime(2026, 7, 6, 14, 0, tzinfo=timezone.utc)
# Mon Jul 6 2026, 21:00 UTC == 17:00 ET -> after close
AFTER_UTC = datetime(2026, 7, 6, 21, 0, tzinfo=timezone.utc)
# Sat Jul 4 2026, 14:00 UTC -> weekend
WEEKEND_UTC = datetime(2026, 7, 4, 14, 0, tzinfo=timezone.utc)
# Fri Jul 3 2026, 14:00 UTC -> holiday (Independence Day observed)
HOLIDAY_UTC = datetime(2026, 7, 3, 14, 0, tzinfo=timezone.utc)


def test_open_during_session():
    assert is_market_open(OPEN_UTC) is True


def test_closed_after_hours():
    assert is_market_open(AFTER_UTC) is False


def test_closed_on_weekend():
    assert is_market_open(WEEKEND_UTC) is False


def test_closed_on_holiday():
    assert is_market_open(HOLIDAY_UTC) is False


def test_brain_is_fable_through_jul7():
    assert brain_model_for(date(2026, 7, 6)) == "claude-fable-5"
    assert brain_model_for(date(2026, 7, 7)) == "claude-fable-5"


def test_brain_is_opus_from_jul8():
    assert brain_model_for(date(2026, 7, 8)) == "claude-opus-4-8"


def test_brain_labels():
    assert brain_label("claude-fable-5") == "Fable 5"
    assert brain_label("claude-opus-4-8") == "Opus 4.8"
