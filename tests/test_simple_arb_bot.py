"""
Tests for SimpleArbitrageBot — real calls to bot methods with mocked I/O.
"""

import asyncio
import time

import pytest
from unittest.mock import MagicMock, patch


def _make_test_bot(make_settings, **settings_overrides):
    """Create a SimpleArbitrageBot with all I/O mocked out."""
    settings = make_settings(**settings_overrides)
    mock_market_info = {
        "market_id": "market-123",
        "yes_token_id": "tok_up",
        "no_token_id": "tok_down",
        "outcomes": ["Up", "Down"],
        "question": "Will BTC go up?",
        "start_date": None,
        "end_date": None,
    }
    mock_client = MagicMock()
    with (
        patch("src.simple_arb_bot.get_client", return_value=mock_client),
        patch(
            "src.simple_arb_bot.fetch_market_from_slug",
            return_value=mock_market_info,
        ),
        patch("src.trading.warmup_client_cache"),
    ):
        from src.simple_arb_bot import SimpleArbitrageBot

        bot = SimpleArbitrageBot(settings, market_slug="btc-updown-15m-1000000")
    return bot


# ---------------------------------------------------------------------------
# _compute_buy_fill  (pure method on bot instance)
# ---------------------------------------------------------------------------


class TestComputeBuyFill:
    def test_single_level_exact_fill(self, make_settings):
        bot = _make_test_bot(make_settings)
        result = bot._compute_buy_fill([(0.50, 10)], 10)
        assert result is not None
        assert result["filled"] == 10
        assert result["vwap"] == pytest.approx(0.50)
        assert result["worst"] == 0.50

    def test_walks_multiple_levels(self, make_settings):
        bot = _make_test_bot(make_settings)
        result = bot._compute_buy_fill([(0.48, 5), (0.50, 5)], 10)
        assert result is not None
        assert result["vwap"] == pytest.approx(0.49)
        assert result["worst"] == 0.50

    def test_insufficient_liquidity(self, make_settings):
        bot = _make_test_bot(make_settings)
        assert bot._compute_buy_fill([(0.50, 3)], 10) is None

    def test_empty_asks(self, make_settings):
        bot = _make_test_bot(make_settings)
        assert bot._compute_buy_fill([], 10) is None

    def test_zero_target(self, make_settings):
        bot = _make_test_bot(make_settings)
        assert bot._compute_buy_fill([(0.50, 10)], 0) is None


# ---------------------------------------------------------------------------
# check_arbitrage
# ---------------------------------------------------------------------------


class TestCheckArbitrage:
    def test_opportunity_found(self, make_settings):
        bot = _make_test_bot(make_settings, order_size=10, target_pair_cost=0.99)
        up_book = {"asks": [(0.48, 10)], "best_bid": 0.47, "best_ask": 0.48}
        down_book = {"asks": [(0.48, 10)], "best_bid": 0.47, "best_ask": 0.48}
        result = bot.check_arbitrage(up_book=up_book, down_book=down_book)
        assert result is not None
        assert result["total_cost"] == pytest.approx(0.96)
        assert result["price_up"] == 0.48
        assert result["price_down"] == 0.48

    def test_no_opportunity(self, make_settings):
        bot = _make_test_bot(make_settings, order_size=10, target_pair_cost=0.99)
        up_book = {"asks": [(0.51, 10)], "best_bid": 0.50, "best_ask": 0.51}
        down_book = {"asks": [(0.51, 10)], "best_bid": 0.50, "best_ask": 0.51}
        assert bot.check_arbitrage(up_book=up_book, down_book=down_book) is None

    def test_no_asks(self, make_settings):
        bot = _make_test_bot(make_settings)
        up_book = {"asks": [], "best_bid": None, "best_ask": None}
        down_book = {"asks": [], "best_bid": None, "best_ask": None}
        assert bot.check_arbitrage(up_book=up_book, down_book=down_book) is None


# ---------------------------------------------------------------------------
# Deal deduplication
# ---------------------------------------------------------------------------


class TestDealDeduplication:
    def test_duplicate_blocked(self, make_settings):
        bot = _make_test_bot(make_settings)
        bot._register_deal(0.48, 0.48)
        assert bot._is_duplicate_deal(0.48, 0.48) is True

    def test_different_prices_allowed(self, make_settings):
        bot = _make_test_bot(make_settings)
        bot._register_deal(0.48, 0.48)
        assert bot._is_duplicate_deal(0.49, 0.47) is False

    def test_expired_deal_allowed(self, make_settings):
        bot = _make_test_bot(make_settings)
        bot._register_deal(0.48, 0.48)
        # Backdate the timestamp so it's expired
        key = bot._deal_key(0.48, 0.48)
        bot._recent_deals[key] = time.time() - 20  # well past the 10s window
        assert bot._is_duplicate_deal(0.48, 0.48) is False


# ---------------------------------------------------------------------------
# Dry-run execution
# ---------------------------------------------------------------------------


class TestDryRunExecution:
    def test_deducts_sim_balance(self, make_settings):
        bot = _make_test_bot(make_settings, dry_run=True, order_size=10)
        bot.sim_balance = 100.0
        bot._last_execution_ts = 0  # no cooldown
        bot.settings.cooldown_seconds = 0
        opportunity = {
            "price_up": 0.48,
            "price_down": 0.48,
            "total_cost": 0.96,
            "total_investment": 9.6,
            "expected_profit": 0.4,
            "profit_pct": 4.17,
            "order_size": 10,
        }
        asyncio.run(bot.execute_arbitrage_async(opportunity))
        assert bot.sim_balance == pytest.approx(90.4)

    def test_increments_counters(self, make_settings):
        bot = _make_test_bot(make_settings, dry_run=True, order_size=10)
        bot.sim_balance = 100.0
        bot._last_execution_ts = 0
        bot.settings.cooldown_seconds = 0
        opportunity = {
            "price_up": 0.48,
            "price_down": 0.48,
            "total_cost": 0.96,
            "total_investment": 9.6,
            "expected_profit": 0.4,
            "profit_pct": 4.17,
            "order_size": 10,
        }
        asyncio.run(bot.execute_arbitrage_async(opportunity))
        assert bot.trades_executed == 1
        assert bot.opportunities_found == 1
