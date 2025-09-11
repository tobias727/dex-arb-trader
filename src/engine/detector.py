from src.config import (
    BINANCE_FEE,
    MIN_EDGE_BPS,
)

class Detector:
    """Responsible for detecting and quantifying arb opportunities"""
    def __init__(self, logger):
        self.logger = logger

    def detect(self, binance_best_bid: int, binance_best_ask: int, uniswap_best_bid: int, uniswap_best_ask: int):
        """Returns (side, net_edge_bps) if opp exists, else False"""
        #if binance_best_ask < uniswap_best_bid:
        if True:
            edge_bps_raw = (uniswap_best_bid * 10_000 // binance_best_ask) - 10_000 # convert to bps
            binance_fee_bps = int(BINANCE_FEE * 10_000)
            gas_cost_abs = 0 # TODO: implement
            net_edge_bps = edge_bps_raw - (binance_fee_bps + gas_cost_abs)

            print(net_edge_bps)
            if net_edge_bps > MIN_EDGE_BPS:
                return "CEX_buy_DEX_sell", net_edge_bps

        if binance_best_bid > uniswap_best_ask:
            edge_bps_raw = (binance_best_bid * 10_000 // uniswap_best_ask) - 10_000 # convert to bps
            binance_fee_bps = int(BINANCE_FEE * 10_000)
            gas_cost_abs = 0 # TODO: implement
            net_edge_bps = edge_bps_raw - (binance_fee_bps + gas_cost_abs)

            if net_edge_bps > MIN_EDGE_BPS:
                return "CEX_sell_DEX_buy", net_edge_bps

        return None, None # no opp
