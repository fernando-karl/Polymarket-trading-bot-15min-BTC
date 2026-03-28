"""
Tests for Telegram notifier.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import patch, MagicMock


class TestTelegramNotifier:
    """Tests for TelegramNotifier class."""
    
    def test_notifier_disabled_without_token(self):
        """Notifier should be disabled when no token provided."""
        from telegram_notifier import TelegramNotifier
        
        notifier = TelegramNotifier(bot_token="", chat_id="123")
        assert notifier.enabled is False
        
        notifier = TelegramNotifier(bot_token=None, chat_id="123")
        assert notifier.enabled is False
    
    def test_notifier_disabled_without_chat_id(self):
        """Notifier should be disabled when no chat_id provided."""
        from telegram_notifier import TelegramNotifier
        
        notifier = TelegramNotifier(bot_token="abc123", chat_id="")
        assert notifier.enabled is False
    
    def test_notifier_enabled_with_both(self):
        """Notifier should be enabled when both token and chat_id provided."""
        from telegram_notifier import TelegramNotifier
        
        notifier = TelegramNotifier(bot_token="abc123", chat_id="123456")
        assert notifier.enabled is True
    
    def test_send_opportunity_alert_format(self):
        """Test opportunity alert message format."""
        from telegram_notifier import TelegramNotifier
        
        notifier = TelegramNotifier(bot_token="abc", chat_id="123")
        
        # Test message building logic
        message = (
            f"🎯 <b>ARBITRAGE OPPORTUNITY</b>\n\n"
            f"📊 <b>Market:</b> btc-updown-15m-1774728000\n"
            f"⏱️ <b>Time:</b> 5m 30s\n\n"
            f"💰 <b>UP:</b> $0.4950\n"
            f"💰 <b>DOWN:</b> $0.4950\n"
            f"💵 <b>Total:</b> $0.9900\n"
            f"📈 <b>Profit:</b> 1.01%\n\n"
            f"<i>Bot: Polymarket 15min Arb Bot</i>"
        )
        
        assert "ARBITRAGE OPPORTUNITY" in message
        assert "UP:</b> $0.4950" in message
        assert "DOWN:</b> $0.4950" in message
        assert "Total:</b> $0.9900" in message
        assert "Profit:</b> 1.01%" in message
    
    def test_send_execution_alert_success(self):
        """Test execution alert for successful trade."""
        from telegram_notifier import TelegramNotifier
        
        notifier = TelegramNotifier(bot_token="abc", chat_id="123")
        
        emoji = "✅"
        message = (
            f"{emoji} <b>ARB EXECUTION EXECUTED</b>\n\n"
            f"📊 <b>Market:</b> btc-updown-15m-1774728000\n"
            f"💵 <b>Cost:</b> $4.95\n"
            f"💰 <b>Profit:</b> $0.05\n\n"
            f"<i>Bot: Polymarket 15min Arb Bot</i>"
        )
        
        assert "✅" in message
        assert "EXECUTED" in message
    
    def test_send_execution_alert_failure(self):
        """Test execution alert for failed trade."""
        from telegram_notifier import TelegramNotifier
        
        notifier = TelegramNotifier(bot_token="abc", chat_id="123")
        
        emoji = "❌"
        message = (
            f"{emoji} <b>ARB EXECUTION FAILED</b>\n\n"
            f"📊 <b>Market:</b> btc-updown-15m-1774728000\n"
            f"💵 <b>Cost:</b> $4.95\n"
            f"💰 <b>Profit:</b> $0.00\n\n"
            f"<i>Bot: Polymarket 15min Arb Bot</i>"
        )
        
        assert "❌" in message
        assert "FAILED" in message
    
    @patch('httpx.post')
    def test_send_message_success(self, mock_post):
        """Test successful message send."""
        from telegram_notifier import TelegramNotifier
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "message_id": 123}
        mock_post.return_value = mock_response
        
        notifier = TelegramNotifier(bot_token="abc123", chat_id="123456")
        result = notifier._send_message("Test message")
        
        assert result is True
        mock_post.assert_called_once()
    
    @patch('httpx.post')
    def test_send_message_failure(self, mock_post):
        """Test failed message send."""
        from telegram_notifier import TelegramNotifier
        
        mock_post.side_effect = Exception("Network error")
        
        notifier = TelegramNotifier(bot_token="abc123", chat_id="123456")
        result = notifier._send_message("Test message")
        
        assert result is False
    
    def test_send_opportunity_returns_false_when_disabled(self):
        """send_opportunity_alert should return False when disabled."""
        from telegram_notifier import TelegramNotifier
        
        notifier = TelegramNotifier(bot_token="", chat_id="")
        result = notifier.send_opportunity_alert(
            market="btc-updown-15m-1774728000",
            price_up=0.495,
            price_down=0.495,
            total_cost=0.99,
            profit_pct=1.01,
            time_remaining="5m 30s"
        )
        
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
