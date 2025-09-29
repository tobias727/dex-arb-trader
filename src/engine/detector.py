import math
from src.config import (
    BINANCE_FEE,
    MIN_EDGE,
)
from src.utils.types import NotionalValues


class Detector:
    """Responsible for detecting and quantifying arb opportunities"""

    def __init__(self, logger):
        self.logger = logger

    def detect(self, notional: NotionalValues):
        """
        Returns (side, net_edge_bps) if opp exists, else False
        uniswap_best_bid: price for 1 input token
        """
        if notional.b_ask < notional.u_bid:
            fee = math.floor(
                notional.b_ask * float(BINANCE_FEE)
            )  # notional binance fee, TODO: check rounding of binance fees
            gas_costs = 0  # TODO: implement
            edge = notional.u_bid - (
                notional.b_ask + fee + gas_costs
            )  # uniswap bid already includes fee

            if edge > MIN_EDGE:
                return "BUY", "SELL", edge  # CEX buy, DEX sell

        if notional.b_bid > notional.u_ask:
            fee = math.floor(
                notional.b_bid * float(BINANCE_FEE)
            )  # notional binance fee
            gas_costs = 0  # TODO: implement
            edge = notional.b_bid - (
                notional.u_ask + fee + gas_costs
            )  # uniswap ask already includes fee

            if edge > MIN_EDGE:
                return "SELL", "BUY", edge  # CEX sell, DEX buy

        return None, None, None  # no opp
