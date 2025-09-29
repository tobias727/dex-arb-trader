from tests.utils.dummy_logger import DummyLogger
from src.engine.detector import Detector
from src.utils.types import NotionalValues


class TestDetector:
    """Test for Arb Detector"""

    detector = Detector(DummyLogger())

    def test_detect_no_opp1(self):
        """Test for no opp scenario"""
        notional = NotionalValues(
            b_bid=44_300_000,
            b_ask=44_300_100,
            u_bid=44_288_000,
            u_ask=44_332_000,
        )
        b_side, u_side, edge = self.detector.detect(notional)

        assert b_side is None
        assert u_side is None
        assert edge is None

    def test_detect_no_opp2(self):
        """Test for no opp scenario when b_ask < u_bid, but fees eats opp"""
        notional = NotionalValues(
            b_bid=44_300_000,
            b_ask=44_300_100,
            u_bid=44_300_200,
            u_ask=44_332_000,
        )

        b_side, u_side, edge = self.detector.detect(notional)

        assert b_side is None
        assert u_side is None
        assert edge is None

    def test_detect_no_opp3(self):
        """Test for no opp scenario when b_bid > u_ask, but fees eats opp"""
        notional = NotionalValues(
            b_bid=44_300_000,
            b_ask=44_300_100,
            u_bid=44_288_200,
            u_ask=44_299_900,
        )

        b_side, u_side, edge = self.detector.detect(notional)

        assert b_side is None
        assert u_side is None
        assert edge is None

    def test_detect_opp1(self):
        """CEX buy, DEX sell Opp"""
        notional = NotionalValues(
            b_bid=44_300_000,
            b_ask=44_300_100,
            u_bid=44_360_000,
            u_ask=44_361_000,
        )

        b_side, u_side, edge = self.detector.detect(notional)

        assert b_side is not None
        assert u_side is not None
        assert edge is not None

    def test_detect_opp2(self):
        """CEX sell, DEX buy Opp"""
        notional = NotionalValues(
            b_bid=44_360_000,
            b_ask=44_360_100,
            u_bid=44_280_000,
            u_ask=44_300_000,
        )

        b_side, u_side, edge = self.detector.detect(notional)

        assert b_side is not None
        assert u_side is not None
        assert edge is not None

    def test_edge_case1(self):
        """very small notionals"""
        notional = NotionalValues(
            b_bid=4,
            b_ask=5,
            u_bid=40,
            u_ask=50,
        )

        b_side, u_side, edge = self.detector.detect(notional)

        assert b_side is not None
        assert u_side is not None
        assert edge is not None
