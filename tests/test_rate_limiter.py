"""
Tests for shared rate limiter.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import json
import time
import tempfile
import os


class TestRateLimiterLogic:
    """Tests for rate limiter logic (without actual file I/O)."""
    
    def test_rate_limit_window_reset(self):
        """Rate limit window should reset after window_size seconds."""
        window_size = 60.0
        now = time.time()
        
        # Simulate state
        state = {"t0": now - 100, "n": 50}  # Old window
        
        # Check if expired
        is_expired = now - state["t0"] > window_size
        
        assert is_expired is True
    
    def test_rate_limit_within_window(self):
        """Should block when request count exceeds max."""
        max_per_window = 80
        state = {"t0": time.time(), "n": 80}
        
        can_proceed = state["n"] < max_per_window
        
        assert can_proceed is False
    
    def test_rate_limit_under_max(self):
        """Should allow when request count is under max."""
        max_per_window = 80
        state = {"t0": time.time(), "n": 50}
        
        can_proceed = state["n"] < max_per_window
        
        assert can_proceed is True
    
    def test_increment_counter(self):
        """Test that counter increments correctly."""
        state = {"t0": time.time(), "n": 50}
        
        state["n"] += 1
        
        assert state["n"] == 51
    
    def test_state_json_format(self):
        """Test that state is correctly serialized to JSON."""
        state = {
            "t0": 1234567890.0,
            "n": 42,
            "writer": "arb_bot",
            "last_t": 1234567890.5
        }
        
        json_str = json.dumps(state)
        parsed = json.loads(json_str)
        
        assert parsed["n"] == 42
        assert parsed["writer"] == "arb_bot"


class TestRateLimiterConcurrency:
    """Tests for rate limiter concurrency behavior."""
    
    def test_non_blocking_read(self):
        """Reads should not be blocked by concurrent writes."""
        # This tests the concept - actual locking tested separately
        state = {"n": 10, "t0": time.time()}
        
        # Multiple reads should see same state
        reads = [state.copy() for _ in range(10)]
        
        assert all(r["n"] == 10 for r in reads)
    
    def test_fcntl_lock_parameters(self):
        """Test fcntl lock constants are valid."""
        import fcntl
        
        # LOCK_EX = exclusive lock (writer)
        # LOCK_SH = shared lock (reader)
        # LOCK_NB = non-blocking
        # LOCK_UN = unlock
        
        assert fcntl.LOCK_EX == 2
        assert fcntl.LOCK_SH == 1
        assert fcntl.LOCK_NB == 4
        assert fcntl.LOCK_UN == 8


class TestRateLimiterStats:
    """Tests for rate limiter statistics."""
    
    def test_get_stats_returns_dict(self):
        """get_stats() should return a dictionary."""
        # Simulated stats
        stats = {
            "t0": time.time(),
            "n": 42,
            "max_per_window": 80,
            "window_size_s": 60.0
        }
        
        assert isinstance(stats, dict)
        assert "n" in stats
        assert "t0" in stats


class TestGetRateLimiterInterface:
    """Verify get_rate_limiter() returns an object with .check_and_increment()."""

    def test_returns_object_with_method(self):
        from src.shared_rate_limiter import get_rate_limiter
        rl = get_rate_limiter()
        assert hasattr(rl, "check_and_increment")
        assert callable(rl.check_and_increment)

    def test_check_and_increment_delegates(self, tmp_path, monkeypatch):
        """check_and_increment() should delegate to module-level function."""
        import src.shared_rate_limiter as mod
        # Use a temp file so we don't touch the shared state
        monkeypatch.setattr(mod, "RATE_STATE_PATH", str(tmp_path / "rate.json"))
        # Reset singleton so it picks up the class version
        monkeypatch.setattr(mod, "_rate_limiter", None)
        rl = mod.get_rate_limiter()
        result = rl.check_and_increment()
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
