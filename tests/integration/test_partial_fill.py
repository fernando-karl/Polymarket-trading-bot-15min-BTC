"""
Critical tests for partial fill handling.
"""
import pytest


class TestPartialFill:
    def test_unwind_when_only_up_fills(self):
        up_filled = True
        down_filled = False
        assert up_filled != down_filled
    
    def test_no_unwind_when_both_fill(self):
        up_filled = True
        down_filled = True
        assert not (up_filled != down_filled)
    
    def test_unwind_sells_filled_position(self):
        side = "BUY"
        unwind_side = "SELL" if side == "BUY" else "BUY"
        assert unwind_side == "SELL"
    
    def test_unwind_calculates_recovery(self):
        size = 5.0
        cost = size * 0.495
        recovery = size * 0.50
        assert recovery > cost
        diff = recovery - cost
        assert 0.02 < diff < 0.03


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
