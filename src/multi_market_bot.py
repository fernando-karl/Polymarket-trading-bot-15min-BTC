#!/usr/bin/env python3
"""
Multi-Market Arbitrage Bot - Entry Point

Run from project root:
    python -m src.multi_market_bot
"""

import asyncio
import logging
import os
import sys
import traceback
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.simple_arb_bot import SimpleArbitrageBot
from src.config import Settings, load_settings
from src.shared_rate_limiter import get_rate_limiter
import httpx
import re

logger = logging.getLogger("multi_market")


class MultiMarketBot:
    """Manages multiple arbitrage bots in parallel."""
    
    def __init__(self, market_slugs: list[str], settings):
        self.market_slugs = market_slugs
        self.settings = settings
        self.bots: dict[str, SimpleArbitrageBot] = {}
        self.tasks: list[asyncio.Task] = []
    
    async def start(self):
        """Start all market bots in parallel."""
        import signal, traceback
        logger.info(f"🚀 Starting Multi-Market Bot for: {', '.join(self.market_slugs)}")
        logger.info(f"PID: {os.getpid()} | Started at: {__import__('datetime').datetime.now().isoformat()}")
        
        # Catch signals for logging
        def log_signal(signum, frame):
            logger.warning(f"⚠️ Signal {signum} received — traceback: {''.join(traceback.format_stack(frame))}")
        for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            try: signal.signal(s, log_signal)
            except: pass
        
        # Create bot for each market
        for slug in self.market_slugs:
            try:
                # Extract market name from slug (e.g., "btc" from "btc-updown-15m-xxx")
                market_name = slug.split("-")[0].upper()
                bot = SimpleArbitrageBot(self.settings, market_slug=slug)
                self.bots[market_name] = bot
                logger.info(f"✅ Bot created for {slug}")
            except Exception as e:
                logger.error(f"❌ Failed to create bot for {slug}: {e}")
        
        if not self.bots:
            logger.error("No bots created, exiting")
            return
        
        # Start all bots in parallel
        bot_tasks = [
            asyncio.create_task(self._run_bot(slug, bot))
            for slug, bot in self.bots.items()
        ]
        
        # Also run market refresh checker
        refresh_task = asyncio.create_task(self._refresh_markets_loop())
        
        # Wait for all tasks
        await asyncio.gather(*bot_tasks, refresh_task)
    
    async def _run_bot(self, slug: str, bot):
        """Run a single bot with error recovery."""
        import traceback
        logger.info(f"🔵 Bot {slug} task started (PID {os.getpid()})")
        while True:
            try:
                await bot.monitor_wss()
            except asyncio.CancelledError:
                logger.info(f"🛑 Bot {slug} cancelled — exiting gracefully")
                raise
            except KeyboardInterrupt:
                logger.info(f"🛑 Bot {slug} interrupted — exiting")
                raise
            except BaseException as e:
                logger.error(f"🚨 Bot {slug} CRASHED ({type(e).__name__}): {e}")
                logger.error(f"   Traceback: {traceback.format_exc()}")
                logger.info(f"Restarting {slug} bot in 5s...")
                await asyncio.sleep(5)
    
    async def _refresh_markets_loop(self):
        """Periodically check if markets need to be refreshed."""
        while True:
            try:
                await asyncio.sleep(60)
                current_markets = await self._get_active_markets()
                
                for market, slug in current_markets.items():
                    if market not in self.bots:
                        logger.info(f"🆕 New market detected: {slug}")
                        try:
                            bot = SimpleArbitrageBot(self.settings, market_slug=slug)
                            self.bots[market] = bot
                            task = asyncio.create_task(self._run_bot(market, bot))
                            self.tasks.append(task)
                        except Exception as e:
                            logger.error(f"Failed to create bot for new market {slug}: {e}")
                
                to_remove = []
                for market in self.bots:
                    if market not in current_markets:
                        logger.info(f"🛑 Market closed: {market}")
                        to_remove.append(market)
                
                for market in to_remove:
                    del self.bots[market]
                    
            except Exception as e:
                logger.error(f"Market refresh error: {e}")
    
    async def _get_active_markets(self) -> dict[str, str]:
        """Get currently active markets from Polymarket."""
        markets = {}
        try:
            resp = httpx.get(
                "https://polymarket.com/crypto/15M",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            now = int(__import__('time').time())
            
            for pattern, name in [
                (r'(btc)-[a-z]+-15m-(\d+)', 'BTC'),
                (r'(eth)-[a-z]+-15m-(\d+)', 'ETH'),
                (r'(sol)-[a-z]+-15m-(\d+)', 'SOL'),
                (r'(bnb)-[a-z]+-15m-(\d+)', 'BNB'),
                (r'(doge)-[a-z]+-15m-(\d+)', 'DOGE'),
                (r'(xrp)-[a-z]+-15m-(\d+)', 'XRP'),
            ]:
                matches = re.findall(pattern, resp.text)
                for prefix, ts in matches:
                    ts = int(ts)
                    remaining = ts + 900 - now
                    if 0 < remaining < 900:
                        slug = f"{prefix}-updown-15m-{ts}"
                        if prefix.upper() not in markets:
                            markets[prefix.upper()] = slug
                            
        except Exception as e:
            logger.error(f"Failed to get active markets: {e}")
        
        return markets


async def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()]
    )
    
    # Load settings
    os.chdir(Path(__file__).parent.parent)
    settings = load_settings()
    
    # Get markets from env or auto-detect
    markets_env = os.getenv("MULTI_MARKET_SLUGS", "")
    if markets_env:
        market_slugs = [s.strip() for s in markets_env.split(",") if s.strip()]
    else:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://polymarket.com/crypto/15M",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            now = int(__import__('time').time())
            markets = {}
            for pattern, name in [
                (r'(btc)-[a-z]+-15m-(\d+)', 'BTC'),
                (r'(eth)-[a-z]+-15m-(\d+)', 'ETH'),
                (r'(sol)-[a-z]+-15m-(\d+)', 'SOL'),
            ]:
                matches = re.findall(pattern, resp.text)
                for prefix, ts in matches:
                    ts = int(ts)
                    remaining = ts + 900 - now
                    if 0 < remaining < 900:
                        slug = f"{prefix}-updown-15m-{ts}"
                        markets[name] = slug
            
            market_slugs = list(markets.values())
            print(f"🎯 Active markets detected: {', '.join(markets.keys())}")
    
    if not market_slugs:
        print("❌ No active markets found")
        return
    
    print(f"🚀 Starting Multi-Market Arbitrage Bot")
    print(f"📊 Markets: {', '.join(market_slugs)}")
    print(f"🔖 Mode: {'🔸 SIMULATION' if settings.dry_run else '🟢 LIVE'}")
    print(f"🎯 Threshold: ${settings.target_pair_cost}")
    print("=" * 60)
    
    bot = MultiMarketBot(market_slugs, settings)
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
