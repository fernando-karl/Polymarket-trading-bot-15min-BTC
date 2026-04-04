"""
Tests for lookup module — fetch_market_from_slug, next_slug, parse_iso.
"""

import json
from datetime import datetime, timezone

import pytest
from unittest.mock import MagicMock, patch

from src.lookup import fetch_market_from_slug, next_slug, parse_iso


# ---------------------------------------------------------------------------
# Helper to build a fake httpx response with __NEXT_DATA__
# ---------------------------------------------------------------------------


def _make_response(slug, *, clob_tokens=None, outcomes=None, extra_markets=None):
    """Build a mock httpx response containing valid __NEXT_DATA__ JSON."""
    if clob_tokens is None:
        clob_tokens = ["tok_yes", "tok_no"]
    if outcomes is None:
        outcomes = ["Up", "Down"]

    market = {
        "id": "market-abc",
        "slug": slug,
        "clobTokenIds": clob_tokens,
        "outcomes": outcomes,
        "question": "Will BTC go up?",
        "startDate": "2026-01-01T00:00:00Z",
        "endDate": "2026-01-01T00:15:00Z",
    }

    markets = [market] + (extra_markets or [])

    payload = {
        "props": {
            "pageProps": {
                "dehydratedState": {
                    "queries": [
                        {
                            "state": {
                                "data": {"markets": markets},
                            }
                        }
                    ]
                }
            }
        }
    }

    html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></html>'
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# fetch_market_from_slug
# ---------------------------------------------------------------------------


class TestFetchMarketFromSlug:
    def test_success(self):
        slug = "btc-updown-15m-1000000"
        resp = _make_response(slug)
        with patch("src.lookup.httpx.get", return_value=resp):
            result = fetch_market_from_slug(slug)
        assert result["market_id"] == "market-abc"
        assert result["yes_token_id"] == "tok_yes"
        assert result["no_token_id"] == "tok_no"

    def test_strips_query_params(self):
        slug = "btc-updown-15m-1000000"
        resp = _make_response(slug)
        with patch("src.lookup.httpx.get", return_value=resp):
            result = fetch_market_from_slug(slug + "?foo=bar")
        assert result["market_id"] == "market-abc"

    def test_missing_next_data_raises(self):
        resp = MagicMock()
        resp.text = "<html><body>No data here</body></html>"
        resp.raise_for_status = MagicMock()
        with patch("src.lookup.httpx.get", return_value=resp):
            with pytest.raises(RuntimeError, match="__NEXT_DATA__"):
                fetch_market_from_slug("btc-updown-15m-1000000")

    def test_slug_not_found_raises(self):
        resp = _make_response("different-slug")
        with patch("src.lookup.httpx.get", return_value=resp):
            with pytest.raises(RuntimeError, match="slug not found"):
                fetch_market_from_slug("btc-updown-15m-999")

    def test_non_binary_market_raises(self):
        slug = "btc-updown-15m-1000000"
        resp = _make_response(
            slug, clob_tokens=["a", "b", "c"], outcomes=["Up", "Down", "Flat"]
        )
        with patch("src.lookup.httpx.get", return_value=resp):
            with pytest.raises(RuntimeError, match="binary"):
                fetch_market_from_slug(slug)


# ---------------------------------------------------------------------------
# next_slug  (pure)
# ---------------------------------------------------------------------------


class TestNextSlug:
    def test_increments_by_900(self):
        assert next_slug("btc-updown-15m-1000") == "btc-updown-15m-1900"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            next_slug("invalid")


# ---------------------------------------------------------------------------
# parse_iso  (pure)
# ---------------------------------------------------------------------------


class TestParseIso:
    def test_parses_z_suffix(self):
        dt = parse_iso("2026-01-01T00:00:00Z")
        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None

    def test_empty_returns_none(self):
        assert parse_iso("") is None
