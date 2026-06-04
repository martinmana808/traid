from tools.fundamentals import (
    compute_peg, classify_pe, classify_growth, classify_margin, classify_health,
)


def test_compute_peg_basic():
    assert compute_peg(30, 30) == 1.0


def test_compute_peg_none_without_growth():
    assert compute_peg(33, None) is None
    assert compute_peg(33, 0) is None
    assert compute_peg(33, -5) is None


def test_compute_peg_none_without_pe():
    assert compute_peg(None, 20) is None


def test_classify_pe_buckets():
    assert classify_pe(None)[0] == "n/a"
    assert classify_pe(12)[0] == "low"
    assert classify_pe(20)[0] == "moderate"
    assert classify_pe(33)[0] == "elevated"
    assert classify_pe(120)[0] == "high"


def test_classify_growth_buckets():
    assert classify_growth(None)[0] == "n/a"
    assert classify_growth(-3)[0] == "shrinking"
    assert classify_growth(3)[0] == "slow"
    assert classify_growth(12)[0] == "solid"
    assert classify_growth(40)[0] == "strong"


def test_classify_margin_buckets():
    assert classify_margin(None)[0] == "n/a"
    assert classify_margin(-5)[0] == "unprofitable"
    assert classify_margin(3)[0] == "thin"
    assert classify_margin(12)[0] == "healthy"
    assert classify_margin(35)[0] == "high"


def test_classify_health_buckets():
    assert classify_health(None)[0] == "n/a"
    assert classify_health(0.3)[0] == "low debt"
    assert classify_health(1.0)[0] == "moderate debt"
    assert classify_health(3.0)[0] == "high debt"
