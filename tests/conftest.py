"""
Pytest configuration and fixtures.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


@pytest.fixture
def make_settings():
    """Factory fixture returning a Settings with safe test defaults."""
    from src.config import Settings

    def _make(**overrides):
        defaults = dict(
            private_key="0x" + "ab" * 32,
            signature_type=2,
            funder="0x" + "cd" * 20,
            dry_run=True,
            order_size=10,
            target_pair_cost=0.99,
            enable_stats=False,
            market_slug="btc-updown-15m-1000000",
        )
        defaults.update(overrides)
        return Settings(**defaults)

    return _make


@pytest.fixture
def mock_clob_client():
    """A MagicMock standing in for ClobClient."""
    client = MagicMock()
    client.get_address.return_value = "0x" + "ab" * 20
    client.create_or_derive_api_creds.return_value = MagicMock(
        api_key="test-key", api_secret="test-secret", api_passphrase="test-pass"
    )
    return client


@pytest.fixture
def patch_trading(mock_clob_client):
    """Patches get_client and rate limiter for all trading.py functions."""
    import src.trading as trading_mod

    trading_mod._cached_client = None
    mock_rl = MagicMock()
    mock_rl.check_and_increment.return_value = True
    with (
        patch("src.trading.get_client", return_value=mock_clob_client),
        patch("src.trading.get_rate_limiter", return_value=mock_rl),
    ):
        yield mock_clob_client
    trading_mod._cached_client = None
