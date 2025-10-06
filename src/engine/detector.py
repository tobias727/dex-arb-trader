from src.config import (
    MIN_EDGE,
)
from src.utils.types import NotionalValues


class Detector:
    """Responsible for detecting and quantifying arb opportunities"""

    def __init__(self, logger):
        self.logger = logger

    def detect(self, notional: NotionalValues):
        """
        Returns (side_cex, side_dex, net_edge_bps) if opp exists, else (None, None, None)
        uniswap_best_bid: price for 1 input token
        """
        edge = notional.u_bid - notional.b_ask
        if edge > MIN_EDGE:
            self.logger.warning("Detected: CEX_buy_DEX_sell, %s", f"{edge:_}")
            return "BUY", "SELL", edge

        edge = notional.b_bid - notional.u_ask
        if edge > MIN_EDGE:
            self.logger.warning("Detected: CEX_sell_DEX_buy, %s", f"{edge:_}")
            return "SELL", "BUY", edge

        return None, None, None  # no opps
