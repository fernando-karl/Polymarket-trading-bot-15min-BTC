"""
Tests for StatisticsTracker — record, stats, persistence, CSV export.
"""

import csv

import pytest

from src.statistics import StatisticsTracker


class TestStatisticsTracker:
    def test_record_trade_computes_fields(self):
        tracker = StatisticsTracker()
        trade = tracker.record_trade(
            market_slug="btc-updown-15m-1000",
            price_up=0.48,
            price_down=0.48,
            total_cost=0.96,
            order_size=10,
        )
        assert trade.total_investment == pytest.approx(9.6)
        assert trade.expected_payout == pytest.approx(10.0)
        assert trade.expected_profit == pytest.approx(0.4)
        assert trade.profit_percentage > 0

    def test_get_stats_empty(self):
        tracker = StatisticsTracker()
        stats = tracker.get_stats()
        assert stats.total_trades == 0
        assert stats.total_invested == 0.0

    def test_get_stats_with_trades(self):
        tracker = StatisticsTracker()
        for _ in range(3):
            tracker.record_trade(
                market_slug="btc-updown-15m-1000",
                price_up=0.48,
                price_down=0.48,
                total_cost=0.96,
                order_size=10,
                filled=True,
            )
        stats = tracker.get_stats()
        assert stats.total_trades == 3
        assert stats.total_invested == pytest.approx(28.8)
        assert stats.total_expected_profit == pytest.approx(1.2)

    def test_save_and_load_roundtrip(self, tmp_path):
        log_file = str(tmp_path / "trades.json")
        tracker = StatisticsTracker(log_file=log_file)
        tracker.record_trade(
            market_slug="btc-updown-15m-1000",
            price_up=0.48,
            price_down=0.48,
            total_cost=0.96,
            order_size=10,
        )
        # Load in a new tracker instance
        tracker2 = StatisticsTracker(log_file=log_file)
        assert len(tracker2.trades) == 1
        assert tracker2.trades[0].market_slug == "btc-updown-15m-1000"

    def test_update_trade_result(self):
        tracker = StatisticsTracker()
        trade = tracker.record_trade(
            market_slug="btc-updown-15m-1000",
            price_up=0.48,
            price_down=0.48,
            total_cost=0.96,
            order_size=10,
        )
        tracker.update_trade_result(trade, market_result="UP", actual_profit=0.4)
        assert trade.actual_profit == 0.4
        assert trade.market_result == "UP"
        stats = tracker.get_stats()
        assert stats.total_actual_profit == pytest.approx(0.4)

    def test_export_csv(self, tmp_path):
        tracker = StatisticsTracker()
        tracker.record_trade(
            market_slug="btc-updown-15m-1000",
            price_up=0.48,
            price_down=0.48,
            total_cost=0.96,
            order_size=10,
        )
        csv_file = str(tmp_path / "trades.csv")
        tracker.export_csv(csv_file)
        with open(csv_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["market_slug"] == "btc-updown-15m-1000"
        assert float(rows[0]["total_investment"]) == pytest.approx(9.6)
