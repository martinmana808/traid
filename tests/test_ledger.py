import json
from pathlib import Path

from tools.ledger import log, list_entries, _next_id


def test_list_entries_empty_when_missing(tmp_path):
    assert list_entries(tmp_path / "nope.jsonl") == []


def test_log_appends_and_lists_roundtrip(tmp_path):
    path = tmp_path / "predictions.jsonl"
    entry = {
        "ticker": "VOO", "market": "US", "type": "long-term",
        "call": "buy", "rationale": "broad market DCA",
        "confidence": "medium", "horizon": "12 months",
        "reference_price": 512.30, "reference_currency": "USD",
    }
    saved = log(entry, path=path, today="2026-06-03")
    assert saved["id"] == "2026-06-03-001"
    assert saved["user_action"] is None
    assert saved["target"] is None

    entries = list_entries(path)
    assert len(entries) == 1
    assert entries[0]["ticker"] == "VOO"
    assert entries[0]["date"] == "2026-06-03"


def test_log_is_append_only_with_sequential_ids(tmp_path):
    path = tmp_path / "predictions.jsonl"
    log({"ticker": "VOO", "call": "buy"}, path=path, today="2026-06-03")
    log({"ticker": "AIR.NZ", "call": "hold"}, path=path, today="2026-06-03")
    log({"ticker": "MSFT", "call": "buy"}, path=path, today="2026-06-04")

    entries = list_entries(path)
    assert [e["id"] for e in entries] == [
        "2026-06-03-001", "2026-06-03-002", "2026-06-04-001",
    ]
    # file has exactly 3 lines (append-only, nothing rewritten)
    assert len([ln for ln in path.read_text().splitlines() if ln.strip()]) == 3


def test_list_entries_respects_limit(tmp_path):
    path = tmp_path / "predictions.jsonl"
    for _ in range(5):
        log({"ticker": "VOO", "call": "buy"}, path=path, today="2026-06-03")
    assert len(list_entries(path, limit=2)) == 2
    assert list_entries(path, limit=2)[-1]["id"] == "2026-06-03-005"


def test_next_id_counts_only_same_date():
    existing = [{"date": "2026-06-03"}, {"date": "2026-06-03"}, {"date": "2026-06-02"}]
    assert _next_id(existing, "2026-06-03") == "2026-06-03-003"
    assert _next_id(existing, "2026-06-04") == "2026-06-04-001"
