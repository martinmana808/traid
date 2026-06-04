from tools.patterns import (
    doji, hammer, shooting_star, bullish_engulfing, bearish_engulfing,
    morning_star, evening_star, find_pivots,
)


def bar(o, h, l, c):
    return {"open": o, "high": h, "low": l, "close": c}


def test_doji_detected_on_tiny_body():
    # open ~ close, real range -> doji
    assert doji([bar(100, 105, 95, 100.2)]) >= 50


def test_doji_absent_on_big_body():
    assert doji([bar(100, 106, 99, 105)]) == 0


def test_hammer_long_lower_shadow():
    # small body up top, long lower shadow, tiny upper shadow
    assert hammer([bar(100, 100.5, 92, 100)]) >= 50


def test_hammer_absent_when_no_lower_shadow():
    assert hammer([bar(100, 106, 99.8, 105)]) == 0


def test_shooting_star_long_upper_shadow():
    assert shooting_star([bar(100, 108, 99.7, 100)]) >= 50


def test_bullish_engulfing():
    prev = bar(100, 100.5, 96, 97)      # red
    cur = bar(96.5, 102, 96, 101)       # green, body engulfs prev body
    assert bullish_engulfing([prev, cur]) >= 50


def test_bearish_engulfing():
    prev = bar(100, 104, 99.5, 103)     # green
    cur = bar(103.5, 104, 98, 99)       # red, engulfs
    assert bearish_engulfing([prev, cur]) >= 50


def test_engulfing_absent_when_inside():
    prev = bar(100, 105, 95, 104)
    cur = bar(101, 103, 100, 102)       # inside prev body -> not engulfing
    assert bullish_engulfing([prev, cur]) == 0


def test_morning_star_bullish_reversal():
    c1 = bar(100, 100.5, 90, 91)        # big red
    c2 = bar(90, 91, 88, 89.5)          # small body
    c3 = bar(90, 98, 89.5, 97)          # big green into c1 body
    assert morning_star([c1, c2, c3]) >= 50


def test_evening_star_bearish_reversal():
    c1 = bar(90, 100, 89.5, 99)         # big green
    c2 = bar(99, 101, 98.5, 100)        # small body
    c3 = bar(99, 99.5, 91, 92)          # big red into c1 body
    assert evening_star([c1, c2, c3]) >= 50


def test_find_pivots_zigzag():
    highs = [1, 2, 3, 2, 1, 2, 3, 4, 3, 2]
    lows = [h - 1 for h in highs]
    piv = find_pivots(highs, lows, window=1)
    assert any(p["kind"] == "high" for p in piv)
    assert any(p["kind"] == "low" for p in piv)
