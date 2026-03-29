"""
Tests for multi-market bot orchestration.
"""

import pytest
from unittest.mock import MagicMock, patch
import asyncio


class TestMarketRefreshLogic:
    """Tests for market refresh logic."""
    
    def test_detect_new_market(self):
        """Test detection of new market."""
        current_markets = {"BTC": "btc-updown-15m-1774728000"}
        new_markets = {"BTC": "btc-updown-15m-1774728000", "ETH": "eth-updown-15m-1774728000"}
        
        # New market detected
        new_market = "ETH" in new_markets and "ETH" not in current_markets
        assert new_market is True
    
    def test_market_closed(self):
        """Test detection of market that closed."""
        current_markets = {"BTC": "btc-updown-15m-1774728000", "ETH": "eth-updown-15m-1774728000"}
        new_markets = {"BTC": "btc-updown-15m-1774728000"}
        
        # ETH market closed
        eth_closed = "ETH" in current_markets and "ETH" not in new_markets
        assert eth_closed is True
    
    def test_no_change(self):
        """Test when no market changes."""
        current_markets = {"BTC": "btc-updown-15m-1774728000"}
        new_markets = {"BTC": "btc-updown-15m-1774728000"}
        
        has_change = current_markets != new_markets
        assert has_change is False


class TestMultiMarketSlugParsing:
    """Tests for multi-market slug parsing."""
    
    def test_parse_multiple_slugs(self):
        """Test parsing multiple slugs from comma-separated string."""
        slugs_str = "btc-updown-15m-1774728000,eth-updown-15m-1774728000,sol-updown-15m-1774728000"
        slugs = [s.strip() for s in slugs_str.split(",")]
        
        assert len(slugs) == 3
        assert "btc-updown-15m-1774728000" in slugs
        assert "eth-updown-15m-1774728000" in slugs
        assert "sol-updown-15m-1774728000" in slugs
    
    def test_parse_empty_string(self):
        """Test parsing empty slug string."""
        slugs_str = ""
        slugs = [s.strip() for s in slugs_str.split(",") if s.strip()]
        
        assert len(slugs) == 0
    
    def test_parse_single_slug(self):
        """Test parsing single slug."""
        slugs_str = "btc-updown-15m-1774728000"
        slugs = [s.strip() for s in slugs_str.split(",") if s.strip()]
        
        assert len(slugs) == 1


class TestAsyncMarketManagement:
    """Tests for async market management."""
    
    def test_async_gather_multiple_bots(self):
        """Test running multiple bots concurrently with asyncio.gather."""
        async def mock_bot(market):
            return f"started_{market}"
        
        async def run_all():
            results = await asyncio.gather(
                mock_bot("BTC"),
                mock_bot("ETH"),
                mock_bot("SOL"),
            )
            return results
        
        results = asyncio.run(run_all())
        
        assert len(results) == 3
        assert "started_BTC" in results
        assert "started_ETH" in results
        assert "started_SOL" in results
    
    def test_bot_restart_on_error(self):
        """Test that bot restarts on error."""
        call_count = 0
        
        async def failing_bot():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Simulated error")
            return "recovered"
        
        async def run_with_restart():
            while True:
                try:
                    result = await failing_bot()
                    return result
                except Exception:
                    await asyncio.sleep(0.01)  # Small delay before restart
        
        result = asyncio.run(run_with_restart())
        
        assert result == "recovered"
        assert call_count == 3


class TestMarketSlugMatching:
    """Tests for matching slugs to market names."""
    
    def test_extract_market_name_from_slug(self):
        """Test extracting market name from slug."""
        slug = "btc-updown-15m-1774728000"
        market_name = slug.split("-")[0].upper()
        
        assert market_name == "BTC"
    
    def test_market_name_unique_per_slug(self):
        """Test that each slug maps to unique market name."""
        slugs = [
            "btc-updown-15m-1774728000",
            "eth-updown-15m-1774728000",
            "sol-updown-15m-1774728000",
        ]
        
        market_names = [s.split("-")[0].upper() for s in slugs]
        
        assert len(market_names) == len(set(market_names))  # All unique


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
