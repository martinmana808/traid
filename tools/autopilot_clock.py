"""US market-open check + date-based brain selection for TRaid Autopilot.

Market hours: Mon-Fri 09:30-16:00 America/New_York, excluding NYSE holidays.
The 2026 holiday set covers the run window (notably Fri Jul 3, the observed
Independence Day, since Jul 4 2026 is a Saturday).
"""
from datetime import date, time
from zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")
_OPEN = time(9, 30)
_CLOSE = time(16, 0)

US_MARKET_HOLIDAYS = {
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Jr. Day
    date(2026, 2, 16),  # Washington's Birthday
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed; Jul 4 is a Saturday)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}


def is_market_open(now_utc):
    ny = now_utc.astimezone(_NY)
    if ny.weekday() >= 5:            # Sat/Sun
        return False
    if ny.date() in US_MARKET_HOLIDAYS:
        return False
    return _OPEN <= ny.time() < _CLOSE


def brain_model_for(ny_date):
    return "claude-fable-5" if ny_date <= date(2026, 7, 7) else "claude-opus-4-8"


def brain_label(model):
    return {"claude-fable-5": "Fable 5", "claude-opus-4-8": "Opus 4.8"}.get(model, model)
