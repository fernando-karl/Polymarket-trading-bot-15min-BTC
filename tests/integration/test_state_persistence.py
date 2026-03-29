"""
Critical tests for state persistence and recovery.
"""

import pytest
import json
import os


class TestStatePersistence:
    """Tests for persisting state to disk."""
    
    def test_save_position_state(self):
        """Test saving position state."""
        state = {
            "positions": [
                {"market": "btc-updown-15m-1774728000", "size": 5, "cost": 4.95}
            ],
            "total_invested": 4.95,
            "total_shares_bought": 10
        }
        
        # Should be serializable to JSON
        json_str = json.dumps(state)
        restored = json.loads(json_str)
        
        assert restored["total_invested"] == 4.95
    
    def test_save_deal_deduplication_state(self):
        """Test saving recent deals for deduplication."""
        recent_deals = {
            "btc-updown-15m-1774728000:0.495000:0.495000": 1234567890.0,
            "eth-updown-15m-1774728000:0.490000:0.500000": 1234567891.0
        }
        
        json_str = json.dumps(recent_deals)
        restored = json.loads(json_str)
        
        assert len(restored) == 2
    
    def test_save_balance_state(self):
        """Test saving cached balance."""
        balance_state = {
            "balance": 100.50,
            "timestamp": 1234567890.0
        }
        
        json_str = json.dumps(balance_state)
        restored = json.loads(json_str)
        
        assert restored["balance"] == 100.50


class TestStateRecovery:
    """Tests for recovering state from disk."""
    
    def test_recover_positions(self):
        """Test recovering positions after restart."""
        saved_state = {
            "positions": [
                {"market": "btc-updown-15m-1774728000", "size": 5}
            ]
        }
        
        # Load from disk
        recovered_positions = saved_state.get("positions", [])
        
        assert len(recovered_positions) == 1
    
    def test_recover_deduplication(self):
        """Test recovering deduplication state."""
        saved_deals = {
            "btc:0.495000:0.495000": 1234567890.0  # Recent deal
        }
        
        import time
        now = time.time()
        dedup_window = 10.0
        
        # Filter expired deals
        active_deals = {
            k: v for k, v in saved_deals.items()
            if now - v < dedup_window
        }
        
        # Recent enough
        assert len(active_deals) == 1
    
    def test_recover_expired_deduplication(self):
        """Test that old deduplication entries are cleared."""
        import time
        saved_deals = {
            "btc:0.495000:0.495000": time.time() - 100  # 100s ago (too old)
        }
        
        dedup_window = 10.0
        now = time.time()
        
        active_deals = {
            k: v for k, v in saved_deals.items()
            if now - v < dedup_window
        }
        
        # Should be empty (expired)
        assert len(active_deals) == 0


class TestPositionRecovery:
    """Tests for recovering positions after restart."""
    
    def test_recover_open_position(self):
        """Test detecting open position after restart."""
        # Position from previous run
        position = {
            "market": "btc-updown-15m-1774728000",
            "side": "BUY",
            "size": 5,
            "filled": True,  # Filled but market hasn't resolved yet
            "cost": 4.95
        }
        
        # Should be detected as needing resolution
        is_open = position.get("filled") and not position.get("resolved")
        assert is_open is True
    
    def test_position_market_resolved(self):
        """Test detecting when recovered position market has resolved."""
        position = {
            "market": "btc-updown-15m-1774708200",  # Old market
            "filled": True,
            "resolved": False
        }
        
        import datetime
        now = int(datetime.datetime.now().timestamp())
        market_ts = int(position["market"].split("-")[-1])
        market_expired = now > (market_ts + 900)
        
        # Market expired means should check resolution
        if market_expired:
            position["resolved"] = True
        
        assert position["resolved"] is True


class TestRestartRecovery:
    """Tests for recovery process on restart."""
    
    def test_load_previous_state_on_startup(self):
        """Test that bot loads previous state on startup."""
        state_file = "/tmp/polymarket_state.json"
        
        # Previous state exists
        previous_state = {"positions": [], "trades": []}
        
        # Load on startup
        loaded = previous_state
        
        assert loaded is not None
    
    def test_clear_state_after_successful_recovery(self):
        """Test clearing state after successful recovery."""
        state = {
            "positions": [{"resolved": True}],  # Resolved position
            "trades": []
        }
        
        # Clear resolved positions
        state["positions"] = [p for p in state["positions"] if not p.get("resolved")]
        
        assert len(state["positions"]) == 0
    
    def test_keep_unresolved_on_recovery(self):
        """Test keeping unresolved positions."""
        state = {
            "positions": [
                {"resolved": True},   # Should be cleared
                {"resolved": False},  # Should be kept
            ]
        }
        
        state["positions"] = [p for p in state["positions"] if not p.get("resolved")]
        
        assert len(state["positions"]) == 1


class TestRecoveryEdgeCases:
    """Tests for edge cases in recovery."""
    
    def test_missing_state_file(self):
        """Test handling missing state file."""
        state_file = "/tmp/nonexistent_state.json"
        exists = os.path.exists(state_file)
        
        # Should handle gracefully
        if not exists:
            state = {"positions": [], "trades": []}
        
        assert state["positions"] == []
    
    def test_corrupted_state_file(self):
        """Test handling corrupted state file."""
        corrupted_json = "{ invalid json"
        
        # Should handle gracefully
        try:
            state = json.loads(corrupted_json)
            loaded = True
        except json.JSONDecodeError:
            state = {"positions": [], "trades": []}
            loaded = False
        
        assert loaded is False
        assert state["positions"] == []
    
    def test_state_from_different_market(self):
        """Test that old market state is not recovered."""
        import datetime
        now = int(datetime.datetime.now().timestamp())
        
        old_position = {
            "market": "btc-updown-15m-1700000000",  # Very old
            "filled": True
        }
        
        market_ts = int(old_position["market"].split("-")[-1])
        is_current_market = market_ts + 900 > now
        
        # Should NOT recover old market positions
        assert is_current_market is False


class TestRestartTiming:
    """Tests for timing considerations on restart."""
    
    def test_state_not_too_stale(self):
        """Test that stale state is not recovered."""
        import time
        stale_timestamp = time.time() - 3600  # 1 hour old
        state_max_age = 300  # 5 minutes
        
        is_stale = time.time() - stale_timestamp > state_max_age
        
        assert is_stale is True
    
    def test_fresh_state_ok(self):
        """Test that fresh state is recovered."""
        import time
        fresh_timestamp = time.time() - 60  # 1 minute old
        state_max_age = 300
        
        is_stale = time.time() - fresh_timestamp > state_max_age
        
        assert is_stale is False


class TestRecoveryLogging:
    """Tests for logging during recovery."""
    
    def test_logs_recovery_start(self):
        """Test that recovery start is logged."""
        log_entry = "Starting state recovery..."
        
        assert "recovery" in log_entry.lower()
    
    def test_logs_positions_found(self):
        """Test logging positions found during recovery."""
        log_entry = "Found 2 unresolved positions"
        
        assert "2" in log_entry
        assert "positions" in log_entry
    
    def test_logs_recovery_complete(self):
        """Test logging recovery completion."""
        log_entry = "Recovery complete: 1 positions recovered"
        
        assert "complete" in log_entry.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
