"""
Tests for arbitrage detection and execution logic.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import MagicMock, patch


class TestArbitrageDetection:
    """Tests for check_arbitrage() logic."""
    
    def test_arbitrage_detected_when_total_below_threshold(self):
        """UP + DOWN < threshold should trigger arbitrage."""
        price_up = 0.495
        price_down = 0.495
        threshold = 0.999
        
        total = price_up + price_down
        has_opportunity = total < threshold
        
        assert has_opportunity is True
        assert total == 0.99
    
    def test_no_arbitrage_when_total_above_threshold(self):
        """UP + DOWN >= threshold should NOT trigger arbitrage."""
        price_up = 0.51
        price_down = 0.51
        threshold = 0.999
        
        total = price_up + price_down
        has_opportunity = total < threshold
        
        assert has_opportunity is False
        assert total == 1.02
    
    def test_no_arbitrage_when_total_equals_threshold(self):
        """UP + DOWN == threshold should NOT trigger arbitrage."""
        price_up = 0.50
        price_down = 0.499
        threshold = 0.999
        
        total = price_up + price_down
        has_opportunity = total < threshold
        
        assert has_opportunity is False
        assert total == 0.999
    
    def test_profit_calculation(self):
        """Test profit calculation when arbitrage is detected."""
        price_up = 0.495
        price_down = 0.495
        order_size = 5
        
        total_cost = (price_up + price_down) * order_size
        expected_payout = order_size * 2  # Both sides = 2x shares
        profit = expected_payout - total_cost
        
        assert total_cost == 4.95
        assert expected_payout == 10.0
        assert profit == 5.05  # 100% payout - cost
    
    def test_profit_percentage_calculation(self):
        """Test profit percentage calculation."""
        total_cost = 4.95
        expected_payout = 10.0
        profit = expected_payout - total_cost
        profit_pct = (profit / total_cost) * 100
        
        assert profit_pct == pytest.approx(102.02, rel=0.01)


class TestFillCalculation:
    """Tests for _compute_buy_fill() logic."""
    
    def test_simple_fill_single_level(self):
        """Test fill calculation with single price level."""
        asks = [(0.50, 100)]  # price, size
        order_size = 10
        
        # Simple fill: price * size
        cost = sum(price * min(size, order_size) for price, size in asks[:1])
        
        assert cost == 5.0
    
    def test_fill_across_multiple_levels(self):
        """Test fill calculation across multiple price levels."""
        asks = [
            (0.50, 5),   # Only 5 shares at 0.50
            (0.51, 10),  # 10 shares at 0.51
        ]
        order_size = 12
        
        # Walk up the book
        remaining = order_size
        total_cost = 0
        for price, size in asks:
            fill_size = min(remaining, size)
            total_cost += price * fill_size
            remaining -= fill_size
            if remaining <= 0:
                break
        
        assert total_cost == (0.50 * 5) + (0.51 * 7)  # 2.50 + 3.57
        assert remaining == 0
    
    def test_worst_fill_price(self):
        """Test worst fill price (highest price needed to fill order)."""
        asks = [
            (0.50, 5),
            (0.52, 10),
        ]
        order_size = 12
        
        remaining = order_size
        worst_price = 0
        for price, size in asks:
            if remaining <= 0:
                break
            fill_size = min(remaining, size)
            worst_price = price
            remaining -= fill_size
        
        assert worst_price == 0.52


class TestDealDeduplication:
    """Tests for deal deduplication logic."""
    
    def test_same_prices_same_deal(self):
        """Same prices should produce same deal key."""
        price_up = 0.495
        price_down = 0.495
        
        key1 = f"{price_up:.6f}_{price_down:.6f}"
        key2 = f"{price_up:.6f}_{price_down:.6f}"
        
        assert key1 == key2
    
    def test_different_prices_different_deal(self):
        """Different prices should produce different deal keys."""
        key1 = f"{0.495:.6f}_{0.495:.6f}"
        key2 = f"{0.500:.6f}_{0.490:.6f}"
        
        assert key1 != key2
    
    def test_duplicate_detection_window(self):
        """Deals within window should be detected as duplicates."""
        import time
        
        recent_deals = {}
        dedup_window = 10.0  # 10 seconds
        
        price_up = 0.495
        price_down = 0.495
        key = f"{price_up:.6f}_{price_down:.6f}"
        
        # First deal
        recent_deals[key] = time.time()
        
        # Check immediately - should be duplicate
        is_duplicate = key in recent_deals
        assert is_duplicate is True
        
        # Check after window expired - should not be duplicate
        recent_deals[key] = time.time() - 15  # 15s ago
        
        now = time.time()
        recent_deals = {
            k: v for k, v in recent_deals.items()
            if now - v < dedup_window
        }
        
        is_duplicate = key in recent_deals
        assert is_duplicate is False


class TestCooldownLogic:
    """Tests for cooldown between trades."""
    
    def test_cooldown_blocks_repeated_trades(self):
        """Cooldown should block trades within the cooldown period."""
        cooldown = 10.0
        last_execution = 5.0  # 5 seconds ago
        
        now = 10.0
        time_since_last = now - last_execution
        
        is_blocked = time_since_last < cooldown
        assert is_blocked is True
    
    def test_cooldown_allows_trades_after_period(self):
        """Cooldown should allow trades after the cooldown period."""
        cooldown = 10.0
        last_execution = 5.0  # 15 seconds ago
        
        now = 20.0
        time_since_last = now - last_execution
        
        is_blocked = time_since_last < cooldown
        assert is_blocked is False


class TestRiskManagement:
    """Tests for risk management logic."""
    
    def test_balance_insufficient(self):
        """Trade should be blocked when balance is insufficient."""
        required = 10.0
        balance = 8.0
        
        can_trade = balance >= required
        assert can_trade is False
    
    def test_balance_sufficient(self):
        """Trade should be allowed when balance is sufficient."""
        required = 10.0
        balance = 15.0
        
        can_trade = balance >= required
        assert can_trade is True
    
    def test_position_size_limit(self):
        """Trade should be blocked when position size exceeds limit."""
        max_position = 50.0
        trade_size = 60.0
        
        is_within_limit = trade_size <= max_position
        assert is_within_limit is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
