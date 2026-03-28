"""
Telegram notifier for arbitrage alerts.
"""

import httpx
import logging
from typing import Optional

logger = logging.getLogger("telegram")


class TelegramNotifier:
    """Sends alerts to Telegram when arbitrage is detected."""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or ""
        self.chat_id = chat_id or ""
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if self.enabled:
            logger.info(f"✅ Telegram notifications enabled (chat_id={self.chat_id})")
        else:
            logger.info("ℹ️ Telegram notifications disabled (no token/chat_id)")
    
    def send_opportunity_alert(
        self,
        market: str,
        price_up: float,
        price_down: float,
        total_cost: float,
        profit_pct: float,
        time_remaining: str,
    ) -> bool:
        """Send arbitrage opportunity alert to Telegram."""
        if not self.enabled:
            return False
        
        message = (
            f"🎯 <b>ARBITRAGE OPPORTUNITY</b>\n\n"
            f"📊 <b>Market:</b> {market}\n"
            f"⏱️ <b>Time:</b> {time_remaining}\n\n"
            f"💰 <b>UP:</b> ${price_up:.4f}\n"
            f"💰 <b>DOWN:</b> ${price_down:.4f}\n"
            f"💵 <b>Total:</b> ${total_cost:.4f}\n"
            f"📈 <b>Profit:</b> {profit_pct:.2f}%\n\n"
            f"<i>Bot: Polymarket 15min Arb Bot</i>"
        )
        
        return self._send_message(message)
    
    def send_execution_alert(
        self,
        market: str,
        status: str,
        total_cost: float,
        profit: float,
    ) -> bool:
        """Send execution result alert to Telegram."""
        if not self.enabled:
            return False
        
        emoji = "✅" if status == "executed" else "❌"
        message = (
            f"{emoji} <b>ARB EXECUTION {status.upper()}</b>\n\n"
            f"📊 <b>Market:</b> {market}\n"
            f"💵 <b>Cost:</b> ${total_cost:.4f}\n"
            f"💰 <b>Profit:</b> ${profit:.4f}\n\n"
            f"<i>Bot: Polymarket 15min Arb Bot</i>"
        )
        
        return self._send_message(message)
    
    def _send_message(self, message: str) -> bool:
        """Send message via Telegram Bot API."""
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            response = httpx.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.debug(f"Telegram notification sent: {response.json()}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False


# Global instance
_notifier: Optional[TelegramNotifier] = None


def get_notifier(bot_token: str = None, chat_id: str = None) -> TelegramNotifier:
    """Get or create Telegram notifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    return _notifier
