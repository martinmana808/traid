from tools.autopilot_news import headlines

RAW = [
    {"content": {
        "title": "Palantir jumps on upgrade",
        "pubDate": "2026-07-02T14:12:51Z",
        "provider": {"displayName": "Yahoo Finance"},
        "canonicalUrl": {"url": "https://example.com/a"},
    }},
    {"content": {
        "title": "Chip demand strong",
        "pubDate": "2026-07-02T13:00:00Z",
        "provider": {"displayName": "Reuters"},
        "clickThroughUrl": {"url": "https://example.com/b"},
    }},
    {"content": {"title": "Third story", "pubDate": "", "provider": {}}},
    {"content": {"title": "Fourth story", "pubDate": "", "provider": {}}},
]


def test_headlines_normalises_and_limits():
    out = headlines("NVDA", limit=3, _fetch=lambda t: RAW)
    assert len(out) == 3
    assert out[0] == {
        "title": "Palantir jumps on upgrade",
        "source": "Yahoo Finance",
        "published": "2026-07-02T14:12:51Z",
        "url": "https://example.com/a",
    }
    assert out[1]["url"] == "https://example.com/b"
    assert out[2]["source"] == ""  # missing provider degrades to empty string


def test_headlines_swallows_errors():
    def boom(_):
        raise RuntimeError("network down")
    assert headlines("NVDA", _fetch=boom) == []


def test_headlines_skips_malformed_items_without_raising():
    bad = [
        {"content": None},
        {"content": "not-a-dict"},
        {"content": {"title": "good", "provider": "not-a-dict", "pubDate": ""}},
        "totally-bad",
    ]
    out = headlines("NVDA", limit=5, _fetch=lambda t: bad)
    # only the one well-formed-enough item survives; provider degrades to ""
    assert out == [{"title": "good", "source": "", "published": "", "url": ""}]
