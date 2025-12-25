from logging import Logger
from state.pool import Pool
from state.orderbook import OrderBook
from engine.executor import Executor
from config import (
    BINANCE_FEE,
)


Q96 = 2**96
UNI_FEE_BPS = 500
UNI_FEE_DEN = 1_000_000
UNI_FEE = UNI_FEE_BPS / UNI_FEE_DEN


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
    def _calc_amount1_with_fee(L, b_bid_sqrt_x96, u_sqrt_price_x96) -> int:
        # Δy = L * (sqrt(P_t) - sqrt(P_c))
        dy_eff = L * (b_bid_sqrt_x96 - u_sqrt_price_x96) // Q96
        dy_in = dy_eff * UNI_FEE_DEN // (UNI_FEE_DEN - UNI_FEE_BPS)
        return dy_in

    @staticmethod
    def _calc_amount0_with_fee(L, b_ask_sqrt_x96, u_sqrt_price_x96) -> int:
        # Δx = L * (1/sqrt(P_t) - 1/sqrt(P_c))
        num = L * Q96 * (u_sqrt_price_x96 - b_ask_sqrt_x96)
        denom = u_sqrt_price_x96 * b_ask_sqrt_x96
        dx_eff = num // denom
        dx_in = dx_eff * UNI_FEE_DEN // (UNI_FEE_DEN - UNI_FEE_BPS)
        return dx_in

    def on_flashblock_done(self, block_number, index):
        """Hook"""
        u_sqrt_price_x96 = self.pool.sqrt_price_x96
        u_L = self.pool.active_liquidity
        u_price = self.pool.price

        b_bid_sqrt_x96 = self.orderbook.bid_sqrt_x96
        b_ask_sqrt_x96 = self.orderbook.ask_sqrt_x96
        b_bid = self.orderbook.bid_price
        b_ask = self.orderbook.ask_price

        if u_sqrt_price_x96 is None:
            self.logger.info("#%s-%s: Waiting for price", block_number, index)
            return

        # fees
        eff_b_buy = b_ask * (1 + BINANCE_FEE)
        eff_b_sell = b_bid * (1 - BINANCE_FEE)

        if eff_b_sell > u_price:
            # Binance SELL, Uniswap BUY
            dy_in = self._calc_amount1_with_fee(u_L, b_bid_sqrt_x96, u_sqrt_price_x96)
            # self.executor.execute_b_sell_u_buy(dy_in, index)

            ##
            edge_abs = eff_b_sell - u_price
            self.logger.info(
                "[B sell / U buy] edge: %.6f USDC/ETH, amount1_in: %.3f USDC",
                edge_abs,
                dy_in / 1e6,
            )

        elif eff_b_buy < u_price:
            # Binance BUY, Uniswap Sell
            dx_in = self._calc_amount0_with_fee(u_L, b_ask_sqrt_x96, u_sqrt_price_x96)
            # self.executor.execute_b_buy_u_sell(dx_in, index)

            ##
            edge_abs = u_price - eff_b_buy
            self.logger.info(
                "[B buy / U sell] edge: %.6f USDC/ETH, amount0_in: %.6f ETH",
                edge_abs,
                dx_in / 1e18,
            )

        else:
            self.logger.info(
                "#%s-%s: B b=%.6f, a=%.6f | U p=%.6f",
                block_number,
                index,
                eff_b_buy,
                eff_b_sell,
                u_price,
            )
