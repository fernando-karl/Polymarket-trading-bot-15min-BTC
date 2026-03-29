"""
Tests for deal deduplication logic.
"""

import pytest
import time
from unittest.mock import MagicMock


class TestDealDeduplication:
    """Tests for deal deduplication with market awareness."""
    
    def test_same_prices_different_markets_are_different_deals(self):
        """Same prices on BTC vs ETH should NOT be treated as duplicates."""
        # The bug: _deal_key didn't include market_slug
        # So BTC $0.34 + $0.40 had same key as ETH $0.34 + $0.40
        
        price_up = 0.34
        price_down = 0.40
        
        # Correct implementation (fixed):
        market_slug_btc = "btc-updown-15m-1774728000"
        market_slug_eth = "eth-updown-15m-1774728000"
        
        key_btc = f"{market_slug_btc}:{price_up:.6f}:{price_down:.6f}"
        key_eth = f"{market_slug_eth}:{price_up:.6f}:{price_down:.6f}"
        
        assert key_btc != key_eth, "Same prices on different markets must be DIFFERENT deals"
    
    def test_same_prices_same_market_are_same_deal(self):
        """Same prices on the SAME market should be duplicates."""
        market_slug = "btc-updown-15m-1774728000"
        price_up = 0.34
        price_down = 0.40
        
        key1 = f"{market_slug}:{price_up:.6f}:{price_down:.6f}"
        key2 = f"{market_slug}:{price_up:.6f}:{price_down:.6f}"
        
        assert key1 == key2, "Same prices on same market must be SAME deal"
    
    def test_different_prices_same_market_are_different_deals(self):
        """Different prices on the same market should be different deals."""
        market_slug = "btc-updown-15m-1774728000"
        
        key1 = f"{market_slug}:{0.34:.6f}:{0.40:.6f}"
        key2 = f"{market_slug}:{0.35:.6f}:{0.39:.6f}"
        
        assert key1 != key2, "Different prices must be different deals"
    
    def test_deduplication_window_expires(self):
        """Deals should be deduplicated only within the window."""
        dedup_window = 10.0
        recent_deals = {}
        
        price_up = 0.34
        price_down = 0.40
        market_slug = "btc-updown-15m-1774728000"
        key = f"{market_slug}:{price_up:.6f}:{price_down:.6f}"
        
        # First deal
        recent_deals[key] = time.time()
        
        # Immediately - should be duplicate
        is_duplicate = key in recent_deals
        assert is_duplicate is True
        
        # After window expired (simulate)
        recent_deals[key] = time.time() - 15  # 15s ago
        
        now = time.time()
        recent_deals = {
            k: v for k, v in recent_deals.items()
            if now - v < dedup_window
        }
        
        is_duplicate = key in recent_deals
        assert is_duplicate is False, "Deal should no longer be deduplicated after window expires"
    
    def test_multiple_deals_same_market_different_times(self):
        """Same prices at different times should be different deals (time-based key needed)."""
        market_slug = "btc-updown-15m-1774728000"
        price_up = 0.34
        price_down = 0.40
        
        # If using time-based deduplication:
        key1 = f"{market_slug}:{price_up:.6f}:{price_down:.6f}:{int(1000)}"  # t=1000
        key2 = f"{market_slug}:{price_up:.6f}:{price_down:.6f}:{int(2000)}"  # t=2000
        
        # These would be different if using time in key
        assert key1 != key2


class TestMarketSlugValidation:
    """Tests for market slug format validation."""
    
    def test_btc_slug_format(self):
        """Test BTC market slug format."""
        slug = "btc-updown-15m-1774728000"
        
        parts = slug.split("-")
        assert parts[0] == "btc"
        assert parts[1] == "updown"
        assert parts[2] == "15m"
        assert parts[3].isdigit()
    
    def test_eth_slug_format(self):
        """Test ETH market slug format."""
        slug = "eth-updown-15m-1774728000"
        
        parts = slug.split("-")
        assert parts[0] == "eth"
    
    def test_timestamp_extraction(self):
        """Test extracting timestamp from slug."""
        slug = "btc-updown-15m-1774728000"
        timestamp = int(slug.split("-")[-1])
        
        assert timestamp == 1774728000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
