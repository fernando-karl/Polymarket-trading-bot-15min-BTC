"""
Tests for trading module — real calls to source functions with mocked I/O.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.trading import (
    extract_order_id,
    get_balance,
    place_order,
    place_orders_fast,
    summarize_order_state,
    wait_for_terminal_order,
)


# ---------------------------------------------------------------------------
# extract_order_id  (pure — no mocking needed)
# ---------------------------------------------------------------------------


class TestExtractOrderId:
    def test_flat_orderID(self):
        assert extract_order_id({"orderID": "abc"}) == "abc"

    def test_flat_orderId(self):
        assert extract_order_id({"orderId": "abc"}) == "abc"

    def test_nested_in_order(self):
        assert extract_order_id({"order": {"orderID": "abc"}}) == "abc"

    def test_nested_in_data(self):
        assert extract_order_id({"data": {"orderId": "abc"}}) == "abc"

    def test_returns_none_for_empty(self):
        assert extract_order_id({}) is None

    def test_returns_none_for_non_dict(self):
        assert extract_order_id("string") is None

    def test_returns_none_for_none(self):
        assert extract_order_id(None) is None


# ---------------------------------------------------------------------------
# summarize_order_state  (pure — no mocking needed)
# ---------------------------------------------------------------------------


class TestSummarizeOrderState:
    def test_filled_order(self):
        result = summarize_order_state({"status": "filled", "filled_size": "10"})
        assert result["status"] == "filled"
        assert result["filled_size"] == 10.0

    def test_status_from_state_key(self):
        result = summarize_order_state({"state": "canceled"})
        assert result["status"] == "canceled"

    def test_filled_computed_from_remaining(self):
        result = summarize_order_state({"original_size": "10", "remaining_size": "3"})
        assert result["filled_size"] == 7.0

    def test_non_dict_input(self):
        result = summarize_order_state("not-a-dict")
        assert result["status"] is None
        assert result["raw"] == "not-a-dict"

    def test_requested_size_passthrough(self):
        result = summarize_order_state({"status": "filled"}, requested_size=50)
        assert result["requested_size"] == 50


# ---------------------------------------------------------------------------
# get_balance  (uses patch_trading fixture)
# ---------------------------------------------------------------------------


class TestGetBalance:
    def test_normal_balance(self, patch_trading, make_settings):
        patch_trading.get_balance_allowance.return_value = {"balance": "50000000"}
        settings = make_settings()
        assert get_balance(settings) == 50.0

    def test_zero_balance(self, patch_trading, make_settings):
        patch_trading.get_balance_allowance.return_value = {"balance": "0"}
        settings = make_settings()
        assert get_balance(settings) == 0.0

    def test_non_dict_response(self, patch_trading, make_settings):
        patch_trading.get_balance_allowance.return_value = "unexpected"
        settings = make_settings()
        assert get_balance(settings) == 0.0

    def test_exception_returns_zero(self, patch_trading, make_settings):
        patch_trading.get_balance_allowance.side_effect = RuntimeError("boom")
        settings = make_settings()
        assert get_balance(settings) == 0.0


# ---------------------------------------------------------------------------
# place_order  (uses patch_trading fixture)
# ---------------------------------------------------------------------------


class TestPlaceOrder:
    def test_success(self, patch_trading, make_settings):
        patch_trading.create_order.return_value = MagicMock(name="signed_order")
        patch_trading.post_order.return_value = {"orderID": "order-1"}
        settings = make_settings()
        result = place_order(
            settings, side="BUY", token_id="tok123", price=0.50, size=10
        )
        assert result == {"orderID": "order-1"}
        patch_trading.create_order.assert_called_once()
        patch_trading.post_order.assert_called_once()

    def test_price_zero_raises(self, patch_trading, make_settings):
        with pytest.raises(ValueError, match="price"):
            place_order(make_settings(), side="BUY", token_id="tok", price=0, size=10)

    def test_size_zero_raises(self, patch_trading, make_settings):
        with pytest.raises(ValueError, match="size"):
            place_order(make_settings(), side="BUY", token_id="tok", price=0.5, size=0)

    def test_empty_token_raises(self, patch_trading, make_settings):
        with pytest.raises(ValueError, match="token_id"):
            place_order(make_settings(), side="BUY", token_id="", price=0.5, size=10)

    def test_invalid_side_raises(self, patch_trading, make_settings):
        with pytest.raises(ValueError, match="side"):
            place_order(
                make_settings(), side="HOLD", token_id="tok", price=0.5, size=10
            )

    def test_rate_limited(self, make_settings, mock_clob_client):
        import src.trading as trading_mod

        trading_mod._cached_client = None
        mock_rl = MagicMock()
        mock_rl.check_and_increment.return_value = False
        with (
            patch("src.trading.get_client", return_value=mock_clob_client),
            patch("src.trading.get_rate_limiter", return_value=mock_rl),
        ):
            with pytest.raises(RuntimeError, match="RATE_LIMIT"):
                place_order(
                    make_settings(), side="BUY", token_id="tok", price=0.5, size=10
                )
        trading_mod._cached_client = None


# ---------------------------------------------------------------------------
# place_orders_fast  (uses patch_trading fixture)
# ---------------------------------------------------------------------------


class TestPlaceOrdersFast:
    def _make_orders(self):
        return [
            {"side": "BUY", "token_id": "tok_up", "price": 0.48, "size": 10},
            {"side": "BUY", "token_id": "tok_down", "price": 0.48, "size": 10},
        ]

    def test_batch_success(self, patch_trading, make_settings):
        patch_trading.create_order.return_value = MagicMock()
        patch_trading.post_orders.return_value = [
            {"orderID": "o1"},
            {"orderID": "o2"},
        ]
        results = place_orders_fast(make_settings(), self._make_orders())
        assert len(results) == 2
        patch_trading.post_orders.assert_called_once()

    def test_parallel_signing_calls_create_order_for_each(self, patch_trading, make_settings):
        """Parallel signing must call create_order once per order."""
        patch_trading.create_order.return_value = MagicMock()
        patch_trading.post_orders.return_value = [{"orderID": "o1"}, {"orderID": "o2"}]
        place_orders_fast(make_settings(), self._make_orders())
        assert patch_trading.create_order.call_count == 2

    def test_batch_fails_falls_back_to_sequential(self, patch_trading, make_settings):
        patch_trading.create_order.return_value = MagicMock()
        patch_trading.post_orders.side_effect = RuntimeError("batch fail")
        patch_trading.post_order.return_value = {"orderID": "seq"}
        results = place_orders_fast(make_settings(), self._make_orders())
        assert len(results) == 2
        assert patch_trading.post_order.call_count == 2

    def test_rate_limited(self, make_settings, mock_clob_client):
        import src.trading as trading_mod

        trading_mod._cached_client = None
        mock_rl = MagicMock()
        mock_rl.check_and_increment.return_value = False
        with (
            patch("src.trading.get_client", return_value=mock_clob_client),
            patch("src.trading.get_rate_limiter", return_value=mock_rl),
        ):
            with pytest.raises(RuntimeError, match="RATE_LIMIT"):
                place_orders_fast(make_settings(), self._make_orders())
        trading_mod._cached_client = None


# ---------------------------------------------------------------------------
# wait_for_terminal_order  (patches get_order)
# ---------------------------------------------------------------------------


class TestWaitForTerminalOrder:
    def test_immediately_filled(self, make_settings):
        settings = make_settings()
        with patch(
            "src.trading.get_order",
            return_value={"status": "filled", "filled_size": "10"},
        ):
            result = wait_for_terminal_order(
                settings, "order-1", requested_size=10, timeout_seconds=1
            )
        assert result["terminal"] is True
        assert result["filled"] is True

    def test_timeout(self, make_settings):
        settings = make_settings()
        with patch(
            "src.trading.get_order",
            return_value={"status": "live", "filled_size": "0"},
        ):
            result = wait_for_terminal_order(
                settings,
                "order-1",
                requested_size=10,
                timeout_seconds=0.3,
                poll_interval_seconds=0.1,
            )
        assert result["terminal"] is False

    def test_canceled_is_terminal(self, make_settings):
        settings = make_settings()
        with patch(
            "src.trading.get_order",
            return_value={"status": "canceled"},
        ):
            result = wait_for_terminal_order(
                settings, "order-1", timeout_seconds=1
            )
        assert result["terminal"] is True
        assert result["filled"] is False
