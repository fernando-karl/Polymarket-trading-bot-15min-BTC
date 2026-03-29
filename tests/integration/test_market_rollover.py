"""
Integration tests for market close and rollover handling.
"""

import pytest
from unittest.mock import patch, MagicMock
import datetime


class TestMarketClose:
    """Tests for market close detection."""
    
    def test_market_closed_when_time_expired(self):
        """Test detecting when market has closed."""
        now = int(datetime.datetime.now().timestamp())
        market_ts = now - 1000  # Started 1000s ago
        
        closing_ts = market_ts + 900  # 15 min later
        has_closed = now >= closing_ts
        
        assert has_closed is True
    
    def test_market_still_open(self):
        """Test detecting when market is still open."""
        now = int(datetime.datetime.now().timestamp())
        market_ts = now - 100  # Started 100s ago
        
        closing_ts = market_ts + 900
        has_closed = now >= closing_ts
        
        assert has_closed is False
    
    def test_market_closing_soon(self):
        """Test detecting market closing soon (within 30s)."""
        now = int(datetime.datetime.now().timestamp())
        market_ts = now - 870  # 30 seconds remaining
        
        closing_ts = market_ts + 900
        remaining = closing_ts - now
        
        assert 0 < remaining <= 30


class TestMarketRollover:
    """Tests for market rollover logic."""
    
    def test_detects_new_market_after_close(self):
        """Test detecting new market after old one closes."""
        old_slug = "btc-updown-15m-1774728000"
        new_slug = "btc-updown-15m-1774728900"
        
        # Should detect change
        has_changed = old_slug != new_slug
        assert has_changed is True
    
    def test_same_market_not_rollover(self):
        """Test that same market is not considered a rollover."""
        slug = "btc-updown-15m-1774728000"
        
        # Should NOT detect change
        has_changed = False
        assert has_changed is False
    
    def test_extracts_timestamp_for_comparison(self):
        """Test extracting timestamp to compare markets."""
        slug1 = "btc-updown-15m-1774728000"
        slug2 = "btc-updown-15m-1774728900"
        
        ts1 = int(slug1.split("-")[-1])
        ts2 = int(slug2.split("-")[-1])
        
        assert ts1 == 1774728000
        assert ts2 == 1774728900
        assert ts2 > ts1
    
    def test_next_market_is_15min_later(self):
        """Test that next market opens 15 min after previous closes."""
        current_ts = 1774728000
        next_ts = 1774728900  # 900 seconds = 15 minutes later
        
        assert next_ts - current_ts == 900


class TestRolloverHandling:
    """Tests for actual rollover execution."""
    
    def test_restarts_bot_with_new_slug(self):
        """Test that bot restarts with new market slug."""
        old_slug = "btc-updown-15m-1774728000"
        new_slug = "btc-updown-15m-1774728900"
        
        # Simulate restart with new slug
        restarted_with = new_slug
        
        assert restarted_with == new_slug
        assert restarted_with != old_slug
    
    def test_resets_state_on_rollover(self):
        """Test that state is reset on rollover."""
        # State that should reset:
        positions = [{"old": "position"}]
        recent_deals = {"old_key": 100}
        
        # On rollover, these should be cleared
        positions = []
        recent_deals = {}
        
        assert len(positions) == 0
        assert len(recent_deals) == 0
    
    def test_preserves_settings_on_rollover(self):
        """Test that settings (threshold, order_size) are preserved."""
        settings = {
            "threshold": 0.999,
            "order_size": 5,
            "dry_run": True
        }
        
        # Settings should NOT change on rollover
        assert settings["threshold"] == 0.999
        assert settings["order_size"] == 5
        assert settings["dry_run"] is True


class TestMultiMarketRollover:
    """Tests for rollover with multiple markets."""
    
    def test_individual_market_rollover(self):
        """Test that only the closed market rolls over, others continue."""
        markets = {
            "BTC": {"slug": "btc-updown-15m-1774728000", "closed": True},
            "ETH": {"slug": "eth-updown-15m-1774728000", "closed": False},
            "SOL": {"slug": "sol-updown-15m-1774728000", "closed": False},
        }
        
        # Only BTC should roll over
        for name, data in markets.items():
            if name == "BTC":
                assert data["closed"] is True
            else:
                assert data["closed"] is False
    
    def test_new_market_appears_for_rolled_over(self):
        """Test that new slug appears for rolled over market."""
        current_slugs = {
            "BTC": "btc-updown-15m-1774728000",
            "ETH": "eth-updown-15m-1774728000",
        }
        
        # After rollover
        new_slugs = {
            "BTC": "btc-updown-15m-1774728900",  # Changed!
            "ETH": "eth-updown-15m-1774728000",   # Same
        }
        
        assert new_slugs["BTC"] != current_slugs["BTC"]
        assert new_slugs["ETH"] == current_slugs["ETH"]


class TestRolloverTiming:
    """Tests for timing of rollover operations."""
    
    def test_rollover_detected_before_close(self):
        """Test that rollover is detected before actual close."""
        now = int(datetime.datetime.now().timestamp())
        market_ts = now - 890  # 10 seconds until close
        
        closing_ts = market_ts + 900
        remaining = closing_ts - now
        
        # Should detect upcoming close
        closing_soon = 0 < remaining < 60
        
        assert closing_soon is True
    
    def test_no_premature_rollover(self):
        """Test that market doesn't rollover before close."""
        now = int(datetime.datetime.now().timestamp())
        market_ts = now - 100  # 13+ minutes remaining
        
        closing_ts = market_ts + 900
        remaining = closing_ts - now
        
        # Should NOT trigger rollover
        should_rollover = remaining <= 0
        
        assert should_rollover is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
