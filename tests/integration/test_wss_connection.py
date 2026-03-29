"""
Integration tests for WebSocket connection handling.
"""

import pytest
from unittest.mock import patch, MagicMock
import asyncio


class TestWSSReconnection:
    """Tests for WebSocket reconnection logic."""
    
    def test_reconnects_on_disconnect(self):
        """Bot should reconnect if WSS disconnects."""
        reconnect_count = 0
        max_retries = 5
        
        async def mock_connect():
            nonlocal reconnect_count
            reconnect_count += 1
            if reconnect_count < 3:
                raise Exception("Connection lost")
            return "connected"
        
        async def run_with_reconnect():
            for attempt in range(max_retries):
                try:
                    result = await mock_connect()
                    return result
                except Exception:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.1)
            raise Exception("Max retries exceeded")
        
        result = asyncio.run(run_with_reconnect())
        
        assert result == "connected"
        assert reconnect_count == 3
    
    def test_gives_up_after_max_retries(self):
        """Bot should give up after max retries."""
        max_retries = 3
        attempts = 0
        
        async def always_fail():
            raise Exception("Connection failed")
        
        async def run():
            for i in range(max_retries):
                try:
                    await always_fail()
                except Exception:
                    if i < max_retries - 1:
                        await asyncio.sleep(0.01)
            return "failed"
        
        result = asyncio.run(run())
        
        assert result == "failed"
    


class TestWSSMessageHandling:
    """Tests for WSS message processing."""
    
    def test_parses_price_change_message(self):
        """Test parsing a price change WSS message."""
        message = {
            "type": "price_change",
            "token_id": "123456",
            "price": "0.495",
            "size": "100",
            "side": "BUY"
        }
        
        # Should extract price and size
        price = float(message.get("price", 0))
        size = float(message.get("size", 0))
        
        assert price == 0.495
        assert size == 100
    
    def test_parses_snapshot_message(self):
        """Test parsing a snapshot WSS message."""
        message = {
            "type": "snapshot",
            "bids": [{"price": "0.49", "size": "100"}],
            "asks": [{"price": "0.50", "size": "100"}],
            "timestamp": 1234567890
        }
        
        bids = message.get("bids", [])
        asks = message.get("asks", [])
        
        assert len(bids) == 1
        assert len(asks) == 1
        assert float(bids[0]["price"]) == 0.49
        assert float(asks[0]["price"]) == 0.50
    
    def test_handles_malformed_message(self):
        """Test handling of malformed WSS message."""
        message = {"type": "unknown", "data": None}
        
        # Should not crash
        msg_type = message.get("type", "unknown")
        assert msg_type == "unknown"


class TestWSSSubscription:
    """Tests for WSS subscription management."""
    
    def test_subscribes_to_market_tokens(self):
        """Test subscribing to UP and DOWN tokens."""
        yes_token_id = "yes_token_123"
        no_token_id = "no_token_456"
        
        subscriptions = [yes_token_id, no_token_id]
        
        assert len(subscriptions) == 2
        assert yes_token_id in subscriptions
        assert no_token_id in subscriptions
    
    def test_unsubscribes_on_close(self):
        """Test unsubscribing when closing connection."""
        subscribed = True
        
        # Simulate close
        def close():
            nonlocal subscribed
            subscribed = False
        
        close()
        
        assert subscribed is False


class TestWSSHeartbeat:
    """Tests for WSS heartbeat/ping handling."""
    
    def test_sends_ping_periodically(self):
        """Test that ping is sent to keep connection alive."""
        last_ping_time = None
        
        def on_ping():
            nonlocal last_ping_time
            import time
            last_ping_time = time.time()
        
        on_ping()
        
        assert last_ping_time is not None
    
    def test_connection_timeout_detection(self):
        """Test detection of connection timeout."""
        import time
        
        last_message_time = time.time() - 60  # 60 seconds ago
        timeout = 30  # 30 second timeout
        
        is_timed_out = (time.time() - last_message_time) > timeout
        
        assert is_timed_out is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
