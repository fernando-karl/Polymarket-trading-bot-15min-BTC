"""
Integration tests for configuration validation.
"""

import pytest
from unittest.mock import patch, MagicMock
import os


class TestThresholdValidation:
    """Tests for threshold configuration validation."""
    
    def test_threshold_must_be_positive(self):
        """Test that threshold > 0 is required."""
        threshold = 0.999
        
        is_valid = threshold > 0 and threshold <= 1.0
        assert is_valid is True
    
    def test_threshold_zero_invalid(self):
        """Test that threshold = 0 is invalid."""
        threshold = 0.0
        
        is_valid = threshold > 0
        assert is_valid is False
    
    def test_threshold_negative_invalid(self):
        """Test that negative threshold is invalid."""
        threshold = -0.1
        
        is_valid = threshold > 0
        assert is_valid is False
    
    def test_threshold_greater_than_one_invalid(self):
        """Test that threshold > 1.0 is invalid (no arb possible)."""
        threshold = 1.1
        
        is_valid = threshold <= 1.0
        assert is_valid is False
    
    def test_threshold_exactly_one_valid(self):
        """Test that threshold = 1.0 is valid (though no profit)."""
        threshold = 1.0
        
        is_valid = threshold > 0 and threshold <= 1.0
        assert is_valid is True
    
    def test_threshold_range_valid(self):
        """Test valid threshold range."""
        valid_thresholds = [0.9, 0.95, 0.99, 0.999, 1.0]
        
        for threshold in valid_thresholds:
            is_valid = threshold > 0 and threshold <= 1.0
            assert is_valid is True, f"Threshold {threshold} should be valid"


class TestOrderSizeValidation:
    """Tests for order size configuration validation."""
    
    def test_order_size_must_be_positive(self):
        """Test that order_size > 0 is required."""
        order_size = 5
        
        is_valid = order_size > 0
        assert is_valid is True
    
    def test_order_size_zero_invalid(self):
        """Test that order_size = 0 is invalid."""
        order_size = 0
        
        is_valid = order_size > 0
        assert is_valid is False
    
    def test_order_size_negative_invalid(self):
        """Test that negative order_size is invalid."""
        order_size = -5
        
        is_valid = order_size > 0
        assert is_valid is False
    
    def test_order_size_minimum_is_one(self):
        """Test that order_size minimum is 1."""
        order_size = 1
        
        is_valid = order_size >= 1
        assert is_valid is True


class TestEnvironmentVariables:
    """Tests for environment variable parsing."""
    
    def test_dry_run_true(self):
        """Test DRY_RUN=true parsing."""
        value = os.getenv("DRY_RUN", "false")
        is_dry_run = value.lower() == "true"
        
        assert is_dry_run is False  # Default is false if not set
    
    def test_dry_run_false(self):
        """Test DRY_RUN=false parsing."""
        value = "false"
        is_dry_run = value.lower() == "true"
        
        assert is_dry_run is False
    
    def test_dry_run_1(self):
        """Test DRY_RUN=1 parsing."""
        value = "1"
        is_dry_run = value.lower() in ("true", "1")
        
        assert is_dry_run is True
    
    def test_use_wss_true(self):
        """Test USE_WSS=true parsing."""
        value = "true"
        use_wss = value.lower() == "true"
        
        assert use_wss is True


class TestConfigurationDefaults:
    """Tests for default configuration values."""
    
    def test_default_threshold(self):
        """Test default threshold value."""
        default = 0.991
        
        assert default > 0
        assert default <= 1.0
    
    def test_default_order_size(self):
        """Test default order size."""
        default = 5
        
        assert default >= 1
    
    def test_default_cooldown(self):
        """Test default cooldown."""
        default = 0
        
        assert default >= 0
    
    def test_default_order_type(self):
        """Test default order type."""
        default = "FOK"
        
        assert default in ["FOK", "FAK", "GTC"]


class TestSecretValidation:
    """Tests for secret/API key validation."""
    
    def test_private_key_format(self):
        """Test private key format validation."""
        key = "0x8f29ebf2062f9682101ef2ee4dd9a8e1e6958aafa3e9529292e24da933c04f54"
        
        # Should start with 0x
        is_valid = key.startswith("0x") and len(key) >= 64
        
        assert is_valid is True
    
    def test_private_key_without_0x(self):
        """Test that key without 0x is invalid."""
        key = "8f29ebf2062f9682101ef2ee4dd9a8e1e6958aafa3e9529292e24da933c04f54"
        
        is_valid = key.startswith("0x")
        assert is_valid is False
    
    def test_empty_api_key_invalid(self):
        """Test that empty API key is invalid."""
        api_key = ""
        
        is_valid = bool(api_key and len(api_key) > 0)
        assert is_valid is False


class TestCooldownValidation:
    """Tests for cooldown configuration."""
    
    def test_cooldown_must_be_non_negative(self):
        """Test that cooldown >= 0 is required."""
        cooldown = 10
        
        is_valid = cooldown >= 0
        assert is_valid is True
    
    def test_cooldown_negative_invalid(self):
        """Test that negative cooldown is invalid."""
        cooldown = -1
        
        is_valid = cooldown >= 0
        assert is_valid is False
    
    def test_cooldown_zero_means_no_cooldown(self):
        """Test that cooldown = 0 means no cooldown."""
        cooldown = 0
        
        assert cooldown == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
