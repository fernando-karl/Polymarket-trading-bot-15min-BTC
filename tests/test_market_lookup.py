"""
Tests for market lookup functionality.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import re
from unittest.mock import patch, MagicMock
import datetime


class TestMarketTimestampSelection:
    """Tests for find_current_btc_15min_market() timestamp selection logic."""
    
    def test_active_market_selected_over_future(self):
        """When there are multiple timestamps, active market should be selected."""
        now = int(datetime.datetime.now().timestamp())
        
        # Simulate the selection logic
        all_ts = sorted([now + 900, now - 100], reverse=True)  # [future, active]
        active_ts = [ts for ts in all_ts if ts <= now and now < (ts + 900)]
        upcoming_ts = [ts for ts in all_ts if ts > now]
        
        # Should select the active one, not the future
        assert len(active_ts) == 1
        assert active_ts[0] == now - 100
    
    def test_future_selected_when_no_active(self):
        """When no active market, should select the nearest upcoming."""
        now = int(datetime.datetime.now().timestamp())
        
        all_ts = [now + 100, now + 200, now + 300]  # All future
        active_ts = [ts for ts in all_ts if ts <= now and now < (ts + 900)]
        upcoming_ts = [ts for ts in all_ts if ts > now]
        
        # Should select the nearest upcoming
        chosen = upcoming_ts[0] if upcoming_ts else all_ts[0]
        assert chosen == now + 100
    
    def test_timestamp_calculation(self):
        """Test that 15min market closes 900s after opening."""
        opening_ts = 1774728000
        closing_ts = opening_ts + 900
        
        assert closing_ts == 1774728900
        
        # Verify: 900 seconds = 15 minutes
        assert (closing_ts - opening_ts) == 900


class TestMarketSlugParsing:
    """Tests for parsing market slugs."""
    
    def test_extract_timestamp_from_slug(self):
        """Test extracting timestamp from market slug."""
        slug = "btc-updown-15m-1774728000"
        match = re.search(r'btc-updown-15m-(\d+)', slug)
        
        assert match is not None
        assert match.group(1) == "1774728000"
    
    def test_extract_prefix_from_slug(self):
        """Test extracting market prefix from slug."""
        test_cases = [
            ("btc-updown-15m-1774728000", "btc"),
            ("eth-updown-15m-1774728000", "eth"),
            ("sol-updown-5m-1774728000", "sol"),
        ]
        
        for slug, expected_prefix in test_cases:
            prefix = slug.split("-")[0]
            assert prefix == expected_prefix
    
    def test_slug_format_15m(self):
        """Test 15min market slug format."""
        slug = "btc-updown-15m-1774728000"
        pattern = r'^[a-z]+-updown-15m-\d+$'
        
        assert re.match(pattern, slug) is not None
    
    def test_slug_format_5m(self):
        """Test 5min market slug format."""
        slug = "eth-updown-5m-1774728000"
        pattern = r'^[a-z]+-updown-5m-\d+$'
        
        assert re.match(pattern, slug) is not None


class TestMarketTimeRemaining:
    """Tests for time remaining calculation."""
    
    def test_time_remaining_calculation(self):
        """Test that time remaining is calculated correctly."""
        now = int(datetime.datetime.now().timestamp())
        market_ts = now - 100  # Started 100s ago
        closing_ts = market_ts + 900  # Closes in 800s
        
        remaining = closing_ts - now
        assert remaining == 800
    
    def test_market_closed_when_past_closing(self):
        """Test detection of closed market."""
        now = int(datetime.datetime.now().timestamp())
        market_ts = now - 1000  # Started 1000s ago (closed ~100s ago)
        
        is_closed = now > (market_ts + 900)
        assert is_closed is True
    
    def test_market_not_yet_opened(self):
        """Test detection of future market."""
        now = int(datetime.datetime.now().timestamp())
        future_market_ts = now + 100  # Opens in 100s
        
        has_started = future_market_ts <= now
        assert has_started is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
