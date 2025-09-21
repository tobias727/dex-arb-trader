import math
from src.config import (
    BINANCE_FEE,
    MIN_EDGE,
    TOKEN0_INPUT,
    BINANCE_TICK_SIZE,
    TOKEN1_DECIMALS,
)

class Detector:
    """Responsible for detecting and quantifying arb opportunities"""
    def __init__(self, logger):
        self.logger = logger

    def detect(self, binance_bid_notional: int, binance_ask_notional: int, uniswap_bid_notional: int, uniswap_ask_notional: int):
        """
        Returns (side, net_edge_bps) if opp exists, else False
        uniswap_best_bid: price for 1 input token
        """
        if binance_ask_notional < uniswap_bid_notional:
            fee = math.floor(binance_ask_notional * float(BINANCE_FEE)) # notional binance fee, TODO: check rounding of binance fees
            gas_costs = 0 # TODO: implement
            edge = uniswap_bid_notional - (binance_ask_notional + fee + gas_costs) # uniswap bid already includes fee
            # self.logger.info(
            #     f"\nu_bid_notional: {uniswap_bid_notional:_.0f}, "
            #     f"b_ask_notional: {binance_ask_notional:_.0f}"
            # )
            # self.logger.info(
            #     f"edge: {edge:_.0f}, fee: {fee:_.0f}, gas_costs: {gas_costs:_.0f}"
            # )
            if edge > MIN_EDGE:
                return "CEX_buy_DEX_sell", edge

        if binance_bid_notional > uniswap_ask_notional:
            fee = math.floor(binance_bid_notional * float(BINANCE_FEE)) # notional binance fee
            gas_costs = 0 # TODO: implement
            edge = binance_bid_notional - (uniswap_ask_notional + fee + gas_costs) # uniswap ask already includes fee
            # self.logger.info(
            #     f"\nb_bid_notional: {binance_bid_notional:_.0f}, "
            #     f"u_ask_notional: {uniswap_ask_notional:_.0f}"
            # )
            # self.logger.info(
            #     f"edge: {edge:_.0f}, fee: {fee:_.0f}, gas_costs: {gas_costs:_.0f}"
            # )
            if edge > MIN_EDGE:
                return "CEX_sell_DEX_buy", edge

        return None, None # no opp
