from logging import Logger
import math
from state.pool import Pool
from state.orderbook import OrderBook
from engine.executor import Executor
from infra.monitoring import append_row_to_csv
from config import (
    BINANCE_FEE,
)


Q96 = 2**96
UNI_FEE_BPS = 500
UNI_FEE_DEN = 1_000_000
UNI_FEE = UNI_FEE_BPS / UNI_FEE_DEN
DEC0 = 18  # ETH
DEC1 = 6  # USDC
SCALE = 10 ** (DEC0 - DEC1)


class ArbDetector:
    """Detects arbitrage opportunities and calls execute"""

    __slots__ = ("pool", "orderbook", "executor", "logger")

    def __init__(
        self, pool: Pool, orderbook: OrderBook, executor: Executor, logger: Logger
    ):
        self.pool = pool
        self.orderbook = orderbook
        self.executor = executor
        self.logger = logger

    @staticmethod
    def _calc_amount1_with_fee(L: int, p_t_sqrt_x96: int, u_sqrt_price_x96: int) -> int:
        # Δy = L * (sqrt(P_t) - sqrt(P_c))
        dy_eff = L * (p_t_sqrt_x96 - u_sqrt_price_x96) // Q96
        dy_in = dy_eff * UNI_FEE_DEN // (UNI_FEE_DEN - UNI_FEE_BPS)
        return dy_in

    @staticmethod
    def _calc_amount0_with_fee(L: int, p_t_sqrt_x96: int, u_sqrt_price_x96: int) -> int:
        # Δx = L * (1/sqrt(P_t) - 1/sqrt(P_c))
        num = L * Q96 * (u_sqrt_price_x96 - p_t_sqrt_x96)
        denom = u_sqrt_price_x96 * p_t_sqrt_x96
        dx_eff = num // denom
        dx_in = dx_eff * UNI_FEE_DEN // (UNI_FEE_DEN - UNI_FEE_BPS)
        return dx_in

    @staticmethod
    def _price_to_sqrt_x96(p: float) -> int:
        raw = p / SCALE
        return int(math.sqrt(raw) * Q96)

    def on_flashblock_done(self, block_number: int, index: int) -> None:
        """Hook to detect arbitrage opportunities"""
        u_sqrt_price_x96 = self.pool.sqrt_price_x96
        if u_sqrt_price_x96 is None:
            self.logger.info("#%s-%s: Waiting for price", block_number, index)
            return

        u_L = self.pool.active_liquidity
        u_price = self.pool.price

        b_bid = self.orderbook.bid_price
        b_ask = self.orderbook.ask_price

        # uni fees
        u_bid = u_price * (1 - UNI_FEE)
        u_ask = u_price / (1 - UNI_FEE)

        # binance fees, given commission asset is BNB
        eff_b_sell = b_bid * (1 - BINANCE_FEE)
        eff_b_buy = b_ask * (1 + BINANCE_FEE)
        # if commission asset is in output token, following applies:
        # eff_b_buy = b_ask / (1 - BINANCE_FEE)
        # eff_b_sell remains same

        sell_edge = eff_b_sell - u_ask
        buy_edge = u_bid - eff_b_buy

        if sell_edge > 0:
            # Binance SELL, Uniswap BUY
            # eff_b_sell = P_t / (1 - UNI_FEE) → P_t = eff_b_sell * (1 - UNI_FEE)
            p_t = eff_b_sell * (1 - UNI_FEE)
            p_t_sqrt_x96 = self._price_to_sqrt_x96(p_t)
            dy_in = self._calc_amount1_with_fee(u_L, p_t_sqrt_x96, u_sqrt_price_x96)

            self.executor.execute_b_sell_u_buy(dy_in, block_number, index)
            self.logger.info(
                "[B sell / U buy] edge: %.6f USDC/ETH, amount1_in: %.3f USDC",
                sell_edge,
                dy_in / 1e6,
            )
            append_row_to_csv(
                "edges.csv",
                {
                    "block": block_number,
                    "fb_index": index,
                    "b_side": "SELL",
                    "edge": sell_edge,
                    "d_in": dy_in / 1e6,
                },
            )

        elif buy_edge > 0:
            # Binance BUY, Uniswap Sell
            # eff_b_buy = P_t * (1 - UNI_FEE) → P_t = eff_b_buy / (1 - UNI_FEE)
            p_t = eff_b_buy / (1 - UNI_FEE)
            p_t_sqrt_x96 = self._price_to_sqrt_x96(p_t)
            dx_in = self._calc_amount0_with_fee(u_L, p_t_sqrt_x96, u_sqrt_price_x96)

            self.executor.execute_b_buy_u_sell(dx_in, block_number, index)
            self.logger.info(
                "[B buy / U sell] edge: %.6f USDC/ETH, amount0_in: %.6f ETH",
                buy_edge,
                dx_in / 1e18,
            )
            append_row_to_csv(
                "edges.csv",
                {
                    "block": block_number,
                    "fb_index": index,
                    "b_side": "BUY",
                    "edge": buy_edge,
                    "d_in": dx_in / 1e18,
                },
            )

        self.logger.info(
            "#%s-%s: B b=%.6f, a=%.6f | U b=%.6f, a=%.6f",
            block_number,
            index,
            eff_b_sell,
            eff_b_buy,
            u_bid,
            u_ask,
        )
