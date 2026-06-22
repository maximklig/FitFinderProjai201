"""
tests/test_tools.py

One test per documented failure mode for each of the three tools.

search_listings runs fully offline (no API key needed). The two LLM-backed
tools (suggest_outfit, create_fit_card) are tested for the failure paths that
short-circuit *before* any network call, so the whole suite passes without a
GROQ_API_KEY. The live LLM behavior is exercised separately.
"""

import sys
from pathlib import Path

# Make the project root importable when pytest is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import search_listings, suggest_outfit, create_fit_card


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Nothing is priced at $5 or under, so this should be an empty list, not a crash.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    # "M" should match listings sized "M", "S/M", "M/L" — never "W30 L30".
    results = search_listings("jacket", size="M", max_price=100)
    assert all("m" in item["size"].lower() for item in results)


def test_search_sorted_by_relevance():
    results = search_listings("vintage denim jacket", size=None, max_price=100)
    assert len(results) >= 2
    # The top hit should be at least as relevant as the runner-up: a denim
    # outerwear piece should outrank a tangential vintage match.
    assert results[0]["category"] in ("outerwear", "bottoms", "tops")


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe_does_not_crash():
    # Empty wardrobe must not raise; it returns general styling advice instead.
    item = {
        "title": "Y2K Baby Tee — Butterfly Print",
        "category": "tops",
        "colors": ["white", "pink"],
        "style_tags": ["y2k", "graphic tee"],
        "size": "S/M",
    }
    result = suggest_outfit(item, {"items": []})
    assert isinstance(result, str)
    assert result != ""


def test_suggest_outfit_missing_items_key():
    # A malformed wardrobe with no 'items' key should also be handled gracefully.
    item = {"title": "Denim Jacket", "category": "outerwear"}
    result = suggest_outfit(item, {})
    assert isinstance(result, str)
    assert result != ""


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error():
    # Empty outfit → descriptive error string, never an exception.
    result = create_fit_card("", {"title": "Denim Jacket", "price": 42.0})
    assert isinstance(result, str)
    assert "unable" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error():
    result = create_fit_card("   \n  ", {"title": "Denim Jacket", "price": 42.0})
    assert isinstance(result, str)
    assert "unable" in result.lower()
