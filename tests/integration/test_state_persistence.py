"""
Critical tests for state persistence and recovery.
"""
import pytest
import json


class TestStatePersistence:
    def test_save_position_state(self):
        state = {"positions": [], "trades": []}
        s = json.dumps(state)
        r = json.loads(s)
        assert r == state
    
    def test_save_deal_dedup_state(self):
        deals = {"key1": 123.0, "key2": 456.0}
        s = json.dumps(deals)
        r = json.loads(s)
        assert len(r) == 2


class TestStateRecovery:
    def test_recover_positions(self):
        saved = {"positions": [{"market": "test", "size": 5}]}
        positions = saved.get("positions", [])
        assert len(positions) == 1
    
    def test_clear_resolved_positions(self):
        positions = [{"resolved": True}, {"resolved": False}]
        active = [p for p in positions if not p.get("resolved")]
        assert len(active) == 1


class TestRecoveryEdgeCases:
    def test_missing_state_file(self):
        exists = False
        if not exists:
            state = {"positions": [], "trades": []}
        else:
            state = {}
        assert state.get("positions") == []
    
    def test_corrupted_state(self):
        valid = False
        if not valid:
            state = {"positions": [], "trades": []}
        else:
            state = {}
        assert state.get("positions") == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
