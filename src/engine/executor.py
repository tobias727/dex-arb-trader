from datetime import datetime
from logging import Logger
import asyncio
from typing import Callable, Awaitable

from clients.binance_client import BinanceClient
from clients.uniswap_client import UniswapClient
from state.balances import Balances
from state.flashblocks import FlashblockBuffer
from utils.utils import calculate_pnl

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
        "flashblock_buffer",
        "_exec_in_progress",
    )

    def __init__(
        self,
        balances: Balances,
        logger: Logger,
        fetch_balances: FetchBalancesFn,
        binance_client: BinanceClient,
        uniswap_client: UniswapClient,
        flashblock_buffer: FlashblockBuffer,
    ):
        self.balances = balances
        self.logger = logger
        self.fetch_balances = fetch_balances
        self.binance_client = binance_client
        self.uniswap_client = uniswap_client
        self.flashblock_buffer = flashblock_buffer
        self._exec_in_progress = False

    def execute_b_sell_u_buy(self, dy_in, flashblock_index):
        """Delegates execution given dy_in (USDC)"""
        if self._exec_in_progress:
            self.logger.warning(
                "Execution skipped: post_execute_hook still running (b_sell_u_buy, flashblock_index=%s)",
                flashblock_index,
            )
            return
        asyncio.create_task(self._guarded_execute(False, flashblock_index))

    def execute_b_buy_u_sell(self, dx_in, flashblock_index):
        """Delegates execution given dx_in (ETH)"""
        if self._exec_in_progress:
            self.logger.warning(
                "Execution skipped: post_execute_hook still running (b_buy_u_sell, flashblock_index=%s)",
                flashblock_index,
            )
            return
        asyncio.create_task(self._guarded_execute(True, flashblock_index))

    async def _guarded_execute(self, zero_for_one: bool, flashblock_index: int):
        self._exec_in_progress = True
        await self._execute(zero_for_one, flashblock_index)
        self._exec_in_progress = False

    async def _execute(self, zero_for_one, flashblock_index):
        # pre-check
        if not self._pre_execute_hook(zero_for_one, flashblock_index):
            return

        # delegate execute to clients
        b_side = "BUY" if zero_for_one else "SELL"
        b_response = await self.binance_client.execute_trade(b_side, 0.002)
        u_receipt = await self.uniswap_client.execute_trade(zero_for_one, 0.002)

        # post-check
        self._post_execute_hook(b_response, u_receipt)

    def _post_execute_hook(self, b_response, u_receipt):
        """Refreshes balances"""
        tx_hash = u_receipt.get("transactionHash")
        fb_info = self.flashblock_buffer.lookup(tx_hash)
        if fb_info is not None:
            block_number, index = fb_info
            self.logger.info(
                "Post-execute status: flashblock=(block=%s, index=%s)\n %s, %s",
                block_number,
                index,
                b_response,
                u_receipt,
            )
        else:
            self.logger.warning(
                "Post-execute status: flashblock not found for tx %s", tx_hash
            )
        # pnl = calculate_pnl(
        #     b_response,
        #     u_receipt,
        # )
        # self.logger.info("Post-execute status: PnL: %s", pnl)
        # TODO: TelegramBot.notify_executed()
        asyncio.create_task(self.fetch_balances())

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
