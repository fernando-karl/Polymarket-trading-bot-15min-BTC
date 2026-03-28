"""
Tests for WebSocket market data handling.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class L2BookState:
    """Copy of L2BookState for testing."""
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    last_timestamp_ms: Optional[int] = None
    last_hash: Optional[str] = None
    _dirty: bool = field(default=True, repr=False)
    _cached_bid_levels: list = field(default_factory=list, repr=False)
    _cached_ask_levels: list = field(default_factory=list, repr=False)
    
    def apply_snapshot(self, msg):
        bids = msg.get("bids") or msg.get("buys") or []
        asks = msg.get("asks") or msg.get("sells") or []
        
        self.bids.clear()
        self.asks.clear()
        
        for lvl in bids:
            try:
                price = float(lvl["price"] if isinstance(lvl, dict) else lvl.price)
                size = float(lvl["size"] if isinstance(lvl, dict) else lvl.size)
            except Exception:
                continue
            if size <= 0:
                continue
            self.bids[price] = size
        
        for lvl in asks:
            try:
                price = float(lvl["price"] if isinstance(lvl, dict) else lvl.price)
                size = float(lvl["size"] if isinstance(lvl, dict) else lvl.size)
            except Exception:
                continue
            if size <= 0:
                continue
            self.asks[price] = size
        
        ts = msg.get("timestamp")
        if ts is not None:
            try:
                self.last_timestamp_ms = int(ts)
            except Exception:
                pass
        self.last_hash = msg.get("hash") or self.last_hash
        self._dirty = True
    
    def apply_price_changes(self, msg):
        ts = msg.get("timestamp")
        if ts is not None:
            try:
                self.last_timestamp_ms = int(ts)
            except Exception:
                pass
        
        for ch in msg.get("price_changes", []) or []:
            try:
                price = float(ch.get("price"))
                size = float(ch.get("size"))
                side = str(ch.get("side", "")).upper()
            except Exception:
                continue
            
            book = self.bids if side == "BUY" else self.asks
            
            if size <= 0:
                book.pop(price, None)
            else:
                book[price] = size
            
            if ch.get("hash"):
                self.last_hash = ch.get("hash")
        
        self._dirty = True
    
    def to_levels(self):
        if not self._dirty:
            return self._cached_bid_levels, self._cached_ask_levels
        
        self._cached_bid_levels = sorted(
            ((p, s) for p, s in self.bids.items() if s > 0),
            key=lambda x: x[0],
            reverse=True
        )
        self._cached_ask_levels = sorted(
            ((p, s) for p, s in self.asks.items() if s > 0),
            key=lambda x: x[0]
        )
        self._dirty = False
        return self._cached_bid_levels, self._cached_ask_levels


class TestL2BookState:
    """Tests for L2BookState class."""
    
    def test_apply_snapshot_single_level(self):
        """Test applying a snapshot with single price level."""
        state = L2BookState()
        msg = {
            "bids": [{"price": "0.50", "size": "100"}],
            "asks": [{"price": "0.51", "size": "100"}],
            "timestamp": 1234567890
        }
        
        state.apply_snapshot(msg)
        
        assert 0.50 in state.bids
        assert state.bids[0.50] == 100.0
        assert 0.51 in state.asks
        assert state.asks[0.51] == 100.0
    
    def test_apply_snapshot_multiple_levels(self):
        """Test applying snapshot with multiple levels."""
        state = L2BookState()
        msg = {
            "bids": [
                {"price": "0.50", "size": "100"},
                {"price": "0.49", "size": "50"},
            ],
            "asks": [
                {"price": "0.51", "size": "75"},
                {"price": "0.52", "size": "25"},
            ]
        }
        
        state.apply_snapshot(msg)
        
        assert len(state.bids) == 2
        assert len(state.asks) == 2
    
    def test_apply_price_changes_add_order(self):
        """Test adding order via price changes."""
        state = L2BookState()
        state.bids = {0.50: 100}
        
        msg = {
            "price_changes": [
                {"price": "0.49", "size": "50", "side": "BUY"}
            ]
        }
        
        state.apply_price_changes(msg)
        
        assert 0.49 in state.bids
        assert state.bids[0.49] == 50.0
    
    def test_apply_price_changes_update_order(self):
        """Test updating order size via price changes."""
        state = L2BookState()
        state.bids = {0.50: 100}
        
        msg = {
            "price_changes": [
                {"price": "0.50", "size": "200", "side": "BUY"}
            ]
        }
        
        state.apply_price_changes(msg)
        
        assert state.bids[0.50] == 200.0
    
    def test_apply_price_changes_remove_order(self):
        """Test removing order via price changes (size=0)."""
        state = L2BookState()
        state.bids = {0.50: 100}
        
        msg = {
            "price_changes": [
                {"price": "0.50", "size": "0", "side": "BUY"}
            ]
        }
        
        state.apply_price_changes(msg)
        
        assert 0.50 not in state.bids
    
    def test_to_levels_sorted_bids_descending(self):
        """Test that bids are sorted descending (highest first)."""
        state = L2BookState()
        state.bids = {0.50: 100, 0.48: 50, 0.52: 75}
        state._dirty = True
        
        bids, _ = state.to_levels()
        
        assert bids[0][0] == 0.52  # Highest price first
        assert bids[1][0] == 0.50
        assert bids[2][0] == 0.48  # Lowest price last
    
    def test_to_levels_sorted_asks_ascending(self):
        """Test that asks are sorted ascending (lowest first)."""
        state = L2BookState()
        state.asks = {0.50: 100, 0.48: 50, 0.52: 75}
        state._dirty = True
        
        _, asks = state.to_levels()
        
        assert asks[0][0] == 0.48  # Lowest price first
        assert asks[1][0] == 0.50
        assert asks[2][0] == 0.52  # Highest price last
    
    def test_dirty_flag_set_on_snapshot(self):
        """Test that dirty flag is set after snapshot."""
        state = L2BookState()
        state._dirty = False
        
        msg = {
            "bids": [{"price": "0.50", "size": "100"}],
            "asks": [{"price": "0.51", "size": "100"}]
        }
        
        state.apply_snapshot(msg)
        
        assert state._dirty is True
    
    def test_dirty_flag_set_on_price_changes(self):
        """Test that dirty flag is set after price changes."""
        state = L2BookState()
        state._dirty = False
        
        msg = {
            "price_changes": [
                {"price": "0.50", "size": "100", "side": "BUY"}
            ]
        }
        
        state.apply_price_changes(msg)
        
        assert state._dirty is True
    
    def test_cached_levels_returned_when_clean(self):
        """Test that cached levels are returned when not dirty."""
        state = L2BookState()
        state._dirty = False
        state._cached_bid_levels = [(0.50, 100)]
        state._cached_ask_levels = [(0.51, 100)]
        
        bids, asks = state.to_levels()
        
        assert bids == [(0.50, 100)]
        assert asks == [(0.51, 100)]
    
    def test_best_bid_and_ask(self):
        """Test extracting best bid and ask from levels."""
        state = L2BookState()
        state.bids = {0.50: 100, 0.48: 50, 0.52: 75}
        state.asks = {0.51: 100, 0.53: 50, 0.49: 75}
        state._dirty = True
        
        bids, asks = state.to_levels()
        
        best_bid = bids[0][0] if bids else None
        best_ask = asks[0][0] if asks else None
        
        assert best_bid == 0.52
        assert best_ask == 0.49


class TestBookFromState:
    """Tests for converting L2BookState to order book format."""
    
    def test_best_bid_ask_extraction(self):
        """Test extracting best bid and ask."""
        state = L2BookState()
        state.bids = {0.52: 75, 0.50: 100, 0.48: 50}
        state.asks = {0.49: 75, 0.51: 100, 0.53: 50}
        state._dirty = True
        
        bids, asks = state.to_levels()
        
        best_bid = bids[0][0] if bids else None  # 0.52
        best_ask = asks[0][0] if asks else None  # 0.49
        
        assert best_bid == 0.52
        assert best_ask == 0.49
        assert best_bid > best_ask  # Spread exists


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
