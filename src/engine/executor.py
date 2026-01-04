from datetime import datetime
import sys
from logging import Logger
import asyncio
from typing import Callable, Awaitable

from clients.binance_client import BinanceClient
from clients.uniswap_client import UniswapClient
from state.balances import Balances

# key: flashblock index (last), value: MS Deadline to be included in flashblock (last) + 1
MAX_MS_PER_INDEX = {
    1: 80,
    2: 350,
    3: 570,
    4: 950,
}

FetchBalancesFn = Callable[[], Awaitable[None]]


class Executor:
    """Does pre-checks and executes binance + uniswap"""

    __slots__ = (
        "balances",
        "logger",
        "fetch_balances",
        "binance_client",
        "uniswap_client",
        "_exec_lock",
    )

    def __init__(
        self,
        balances: Balances,
        logger: Logger,
        fetch_balances: FetchBalancesFn,
        binance_client: BinanceClient,
        uniswap_client: UniswapClient,
    ):
        self.balances = balances
        self.logger = logger
        self.fetch_balances = fetch_balances
        self.binance_client = binance_client
        self.uniswap_client = uniswap_client
        self._exec_lock = asyncio.Lock()

    def execute_b_sell_u_buy(self, dy_in, flashblock_index):
        """Delegates execution given dy_in (USDC)"""
        asyncio.create_task(self._guarded_execute(False, flashblock_index))

    def execute_b_buy_u_sell(self, dx_in, flashblock_index):
        """Delegates execution given dx_in (ETH)"""
        asyncio.create_task(self._guarded_execute(True, flashblock_index))

    async def _guarded_execute(self, zero_for_one: bool, flashblock_index: int):
        async with self._exec_lock:
            await self._execute(zero_for_one, flashblock_index)

    async def _execute(self, zero_for_one, flashblock_index):
        # pre-check
        if not self._pre_execute_hook(zero_for_one, flashblock_index):
            return

        # delegate execute to clients
        b_side = "BUY" if zero_for_one else "SELL"
        b_status = await self.binance_client.execute_trade(b_side, 0.002)
        u_status = await self.uniswap_client.execute_trade(zero_for_one, 0.002)

        # post-check
        self._post_execute_hook(b_status, u_status)

    def _post_execute_hook(self, b_status, u_status):
        """Refreshes balances"""
        # TODO: pnl utils.calculate_pnl()
        # pnl = calculate_pnl(
        #     self.state.last_trade_result["response_binance"],
        #     self.state.last_trade_result["receipt_uniswap"],
        # )
        # TODO: TelegramBot.notify_executed()
        self.logger.info("Post-execute status: %s, %s", b_status, u_status)
        asyncio.create_task(self.fetch_balances())
        sys.exit(0)

    def _pre_execute_hook(self, zero_for_one, flashblock_index):
        """Checks balances + flashblock timings"""
        # balances check
        b = self.balances
        if zero_for_one:
            # B_BUY_U_SELL
            if b.b_usdc < 10 or b.u_eth < 0.002:
                self.logger.warning(
                    "Pre-check: insufficient Balance b_buy_u_sell: b_usdc %s, u_eth %s",
                    b.b_usdc,
                    b.u_eth,
                )
                return False
        else:
            # B_SELL_U_BUY
            if b.b_eth < 0.002 or b.u_usdc < 10:
                self.logger.warning(
                    "Pre-check: insufficient Balance b_sell_u_buy: b_eth %s, u_usdc %s",
                    b.b_eth,
                    b.u_usdc,
                )
                return False

        # flashblock checks
        if flashblock_index == 0:
            self.logger.warning("Pre-check: flashblock_index=0")
            return False
        limit = MAX_MS_PER_INDEX.get(flashblock_index)
        ms = self._current_ms_of_second()
        if ms > limit:
            self.logger.warning("Pre-check: ms > limit, %s > %s", ms, limit)
            return False
        return True

    @staticmethod
    def _current_ms_of_second() -> int:
        now = datetime.now()
        return now.microsecond // 1000
