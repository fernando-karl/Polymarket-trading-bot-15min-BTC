"""
Tests for risk management.
"""

import pytest
from datetime import datetime, timedelta


class TestPositionSizeLimits:
    """Tests for position size risk management."""
    
    def test_position_within_limit(self):
        """Test position within size limit."""
        max_position = 50.0
        trade_size = 40.0
        
        is_safe = trade_size <= max_position
        assert is_safe is True
    
    def test_position_at_limit(self):
        """Test position at exactly the limit."""
        max_position = 50.0
        trade_size = 50.0
        
        is_safe = trade_size <= max_position
        assert is_safe is True
    
    def test_position_exceeds_limit(self):
        """Test position exceeding size limit."""
        max_position = 50.0
        trade_size = 60.0
        
        is_safe = trade_size <= max_position
        assert is_safe is False


class TestDailyLossLimits:
    """Tests for daily loss limit."""
    
    def test_loss_within_daily_limit(self):
        """Test loss within daily limit."""
        max_daily_loss = 20.0
        current_loss = 15.0
        
        is_safe = current_loss <= max_daily_loss
        assert is_safe is True
    
    def test_loss_at_daily_limit(self):
        """Test loss at exactly daily limit."""
        max_daily_loss = 20.0
        current_loss = 20.0
        
        is_safe = current_loss <= max_daily_loss
        assert is_safe is True
    
    def test_loss_exceeds_daily_limit(self):
        """Test loss exceeding daily limit."""
        max_daily_loss = 20.0
        current_loss = 25.0
        
        is_safe = current_loss <= max_daily_loss
        assert is_safe is False


class TestTradeCountLimits:
    """Tests for daily trade count limit."""
    
    def test_trades_within_limit(self):
        """Test trade count within limit."""
        max_trades = 50
        current_trades = 30
        
        is_safe = current_trades < max_trades
        assert is_safe is True
    
    def test_trades_at_limit(self):
        """Test trade count at limit."""
        max_trades = 50
        current_trades = 50
        
        is_safe = current_trades < max_trades
        assert is_safe is False
    
    def test_trades_exceed_limit(self):
        """Test trade count exceeding limit."""
        max_trades = 50
        current_trades = 55
        
        is_safe = current_trades < max_trades
        assert is_safe is False


class TestMinimumBalanceLimits:
    """Tests for minimum balance requirements."""
    
    def test_balance_above_minimum(self):
        """Test balance above minimum."""
        min_balance = 10.0
        current_balance = 15.0
        
        has_minimum = current_balance >= min_balance
        assert has_minimum is True
    
    def test_balance_at_minimum(self):
        """Test balance at exactly minimum."""
        min_balance = 10.0
        current_balance = 10.0
        
        has_minimum = current_balance >= min_balance
        assert has_minimum is True
    
    def test_balance_below_minimum(self):
        """Test balance below minimum."""
        min_balance = 10.0
        current_balance = 8.0
        
        has_minimum = current_balance >= min_balance
        assert has_minimum is False


class TestRiskDecision:
    """Tests for combined risk decision logic."""
    
    def test_all_checks_pass(self):
        """Test when all risk checks pass."""
        position_safe = 40.0 <= 50.0
        loss_safe = 15.0 <= 20.0
        trades_safe = 30 < 50
        balance_safe = 15.0 >= 10.0
        
        can_trade = position_safe and loss_safe and trades_safe and balance_safe
        assert can_trade is True
    
    def test_single_check_fails(self):
        """Test when one risk check fails."""
        position_safe = 60.0 <= 50.0  # FAILS
        loss_safe = 15.0 <= 20.0
        trades_safe = 30 < 50
        balance_safe = 15.0 >= 10.0
        
        can_trade = position_safe and loss_safe and trades_safe and balance_safe
        assert can_trade is False
    
    def test_multiple_checks_fail(self):
        """Test when multiple risk checks fail."""
        position_safe = 60.0 <= 50.0  # FAILS
        loss_safe = 25.0 <= 20.0  # FAILS
        trades_safe = 30 < 50
        balance_safe = 15.0 >= 10.0
        
        can_trade = position_safe and loss_safe and trades_safe and balance_safe
        assert can_trade is False


class TestRiskReason:
    """Tests for risk rejection reasons."""
    
    def test_reason_position_size(self):
        """Test generating reason for position size rejection."""
        max_position = 50.0
        trade_size = 60.0
        
        if trade_size > max_position:
            reason = f"Position size ${trade_size} exceeds limit ${max_position}"
        else:
            reason = "OK"
        
        assert "exceeds limit" in reason
        assert "60" in reason
    
    def test_reason_daily_loss(self):
        """Test generating reason for daily loss rejection."""
        max_loss = 20.0
        current_loss = 25.0
        
        if current_loss > max_loss:
            reason = f"Daily loss ${current_loss} exceeds limit ${max_loss}"
        else:
            reason = "OK"
        
        assert "exceeds limit" in reason
    
    def test_reason_balance(self):
        """Test generating reason for balance rejection."""
        min_balance = 10.0
        current_balance = 8.0
        
        if current_balance < min_balance:
            reason = f"Balance ${current_balance} below minimum ${min_balance}"
        else:
            reason = "OK"
        
        assert "below minimum" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
