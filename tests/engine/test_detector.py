from tests.utils.dummy_logger import DummyLogger
from src.engine.detector import Detector


class TestDetector:
    """Test for Arb Detector"""

    detector = Detector(DummyLogger())

    def test_detect_no_opp1(self):
        """Test for no opp scenario"""
        b_bid_notional = 44_300_000
        b_ask_notional = 44_300_100
        u_bid_notional = 44_288_000
        u_ask_notional = 44_332_000

        side, edge = self.detector.detect(
            b_bid_notional, b_ask_notional, u_bid_notional, u_ask_notional
        )

        assert side is None
        assert edge is None

    def test_detect_no_opp2(self):
        """Test for no opp scenario when b_ask < u_bid, but fees eats opp"""
        b_bid_notional = 44_300_000
        b_ask_notional = 44_300_100
        u_bid_notional = 44_300_200
        u_ask_notional = 44_332_000

        side, edge = self.detector.detect(
            b_bid_notional, b_ask_notional, u_bid_notional, u_ask_notional
        )

        assert side is None
        assert edge is None

    def test_detect_no_opp3(self):
        """Test for no opp scenario when b_bid > u_ask, but fees eats opp"""
        b_bid_notional = 44_300_000
        b_ask_notional = 44_300_100
        u_bid_notional = 44_288_200
        u_ask_notional = 44_299_900

        side, edge = self.detector.detect(
            b_bid_notional, b_ask_notional, u_bid_notional, u_ask_notional
        )

        assert side is None
        assert edge is None

    def test_detect_opp1(self):
        """CEX buy, DEX sell Opp"""
        b_bid_notional = 44_300_000
        b_ask_notional = 44_300_100
        u_bid_notional = 44_360_000
        u_ask_notional = 44_361_000

        side, edge = self.detector.detect(
            b_bid_notional, b_ask_notional, u_bid_notional, u_ask_notional
        )

        assert side is not None
        assert edge is not None

    def test_detect_opp2(self):
        """CEX sell, DEX buy Opp"""
        b_bid_notional = 44_360_000
        b_ask_notional = 44_360_100
        u_bid_notional = 44_280_000
        u_ask_notional = 44_300_000

        side, edge = self.detector.detect(
            b_bid_notional, b_ask_notional, u_bid_notional, u_ask_notional
        )

        assert side is not None
        assert edge is not None

    def test_edge_case1(self):
        """very small notionals"""
        b_bid_notional = 4
        b_ask_notional = 5
        u_bid_notional = 40
        u_ask_notional = 50

        side, edge = self.detector.detect(
            b_bid_notional, b_ask_notional, u_bid_notional, u_ask_notional
        )

        assert side is not None
        assert edge is not None
