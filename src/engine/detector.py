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
            return "BUY", "SELL", edge  # CEX buy, DEX sell

        edge = notional.b_bid - notional.u_ask
        if edge > MIN_EDGE:
            return "SELL", "BUY", edge  # CEX sell, DEX buy

        return None, None, None  # no opps
