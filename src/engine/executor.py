from datetime import datetime
import time
import os
import csv
from logging import Logger
import asyncio
from typing import Callable, Awaitable
from decimal import Decimal, ROUND_DOWN

from clients.binance.client import BinanceClient
from clients.uniswap.client import UniswapClient
from state.balances import Balances
from state.flashblocks import FlashblockBuffer
from infra.monitoring import TelegramBot

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
        "telegram_bot",
    )

    def __init__(
        self,
        balances: Balances,
        logger: Logger,
        fetch_balances: FetchBalancesFn,
        binance_client: BinanceClient,
        uniswap_client: UniswapClient,
        flashblock_buffer: FlashblockBuffer,
        telegram_bot: TelegramBot,
    ):
        self.balances = balances
        self.logger = logger
        self.fetch_balances = fetch_balances
        self.binance_client = binance_client
        self.uniswap_client = uniswap_client
        self.flashblock_buffer = flashblock_buffer
        self.telegram_bot = telegram_bot
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
        b_coro = self.binance_client.execute_trade(b_side, 0.002)
        u_coro = self.uniswap_client.execute_trade(zero_for_one, 0.002)
        b_response, u_receipt = await asyncio.gather(b_coro, u_coro)

        # post-check
        await self._post_execute_hook(b_response, u_receipt)

    async def _post_execute_hook(self, b_response, u_receipt):
        """Refreshes balances"""
        tx_hash_raw = u_receipt.get("transactionHash")
        tx_hash = "0x" + tx_hash_raw.hex()
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
        await self.telegram_bot.notify_executed("PNL_PLACEHOLDER")  # TODO: pnl
        await self.fetch_balances()

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

    @staticmethod
    def _calculate_pnl(response_binance, receipt_uniswap):
        """Function to calculate PnL after execution"""
        # use binance price for gas fee calculation in USDC for simplicity
        eth_to_usdc_price = Decimal(response_binance["fills"][0]["price"])
        # uniswap
        uniswap_usdc_amount = Decimal("0")
        for log in receipt_uniswap["logs"]:
            if (
                log["topics"][0].lower()
                == "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            ):  # Transfer(address,address,uint256)
                uniswap_usdc_amount += Decimal(int(log["data"], 16)) / Decimal(
                    "1000000"
                )  # USDC 6 decimals
        gas_fee_eth = (
            Decimal(int(receipt_uniswap["gasUsed"], 16))
            * Decimal(int(receipt_uniswap["effectiveGasPrice"], 16))
            / Decimal(1e18)
        )
        gas_fee_usdc = gas_fee_eth * Decimal(eth_to_usdc_price)

        # binance
        binance_pnl = Decimal("0")
        if response_binance["side"] == "BUY":
            for fill in response_binance["fills"]:
                price = Decimal(fill["price"])
                qty = Decimal(fill["qty"])
                commission = Decimal(fill["commission"])
                # BUY: commission in ETH, convert to USDC
                binance_pnl -= price * qty
                binance_pnl -= commission * price
        elif response_binance["side"] == "SELL":
            for fill in response_binance["fills"]:
                price = Decimal(fill["price"])
                qty = Decimal(fill["qty"])
                commission = Decimal(fill["commission"])
                # SELL: commission in USDC
                binance_pnl += price * qty
                binance_pnl -= commission

        # total
        if response_binance["side"] == "BUY":
            total_pnl = uniswap_usdc_amount + binance_pnl - gas_fee_usdc
        else:  # b_side == "SELL"
            total_pnl = binance_pnl - uniswap_usdc_amount - gas_fee_usdc
        return total_pnl.quantize(Decimal("1e-6"), rounding=ROUND_DOWN)

    @staticmethod
    def append_trade_to_csv(filename, trade_data):
        """Appends trades to csv file in out/, adds current CET timestamp"""
        cet_time = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        trade_data = {"timestamp": cet_time, **trade_data}
        out_path = os.path.join("out", filename)
        os.makedirs("out", exist_ok=True)
        file_exists = os.path.isfile(out_path)
        with open(out_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=trade_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(trade_data)
