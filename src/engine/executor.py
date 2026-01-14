from datetime import datetime
import time
import os
import csv
from logging import Logger
import asyncio
from typing import Callable, Awaitable
from decimal import Decimal, ROUND_DOWN
from web3.types import TxReceipt
from web3.datastructures import AttributeDict
from web3 import Web3

from clients.binance.client import BinanceClient
from clients.uniswap.client import UniswapClient
from state.balances import Balances
from state.flashblocks import FlashblockBuffer
from infra.monitoring import TelegramBot
from config import (
    TOKEN1_DECIMALS,
)

# key: flashblock index (last), value: MS Deadline to be included in flashblock (last) + 1
MAX_MS_PER_INDEX = {
    1: 80,
    2: 350,
    3: 570,
    4: 950,
}
TOPIC_TRANSFER_EVENT = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)

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
        pnl = self.calculate_pnl(
            b_response,
            u_receipt,
        )
        self.logger.info("Post-execute status: PnL: %s", pnl)
        await self.telegram_bot.notify_executed(pnl)
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
    def calculate_pnl(response_binance: dict, receipt_uniswap: TxReceipt) -> Decimal:
        """Returns PnL in USDC"""
        fill_price, qty, com = Executor._acc_fills(response_binance["fills"])
        notional_price = fill_price * qty
        transfer_out_amount = Executor._get_transfer_amount(receipt_uniswap)
        u_fee_in_eth = Executor._get_transaction_costs(receipt_uniswap)
        if response_binance["side"] == "SELL":
            sell = notional_price
            b_fee = com
            buy = transfer_out_amount
        else:  # Binance Side == "BUY":
            sell = transfer_out_amount
            b_fee = com * fill_price
            buy = notional_price
        u_fee = u_fee_in_eth * fill_price
        total_fees = b_fee + u_fee
        pnl = sell - (buy + total_fees)
        return pnl

    @staticmethod
    def _acc_fills(fills):
        total_notional = Decimal("0")
        total_qty = Decimal("0")
        total_commission = Decimal("0")
        for fill in fills:
            price = Decimal(fill["price"])
            qty = Decimal(fill["qty"])
            commission = Decimal(fill["commission"])
            total_notional += price * qty
            total_qty += qty
            total_commission += commission
        avg_price = total_notional / total_qty if total_qty else Decimal("0")
        return avg_price, total_qty, total_commission

    @staticmethod
    def _get_transfer_amount(tx_receipt: TxReceipt) -> Decimal:
        transfer_topic_log = Executor._extract_transfer_log(tx_receipt)
        transfer_out_raw = int(transfer_topic_log.data.hex(), 16)
        return transfer_out_raw / Decimal(f"1e{TOKEN1_DECIMALS}")

    @staticmethod
    def _extract_transfer_log(tx_receipt: TxReceipt) -> AttributeDict | None:
        for log in tx_receipt["logs"]:
            topics = log["topics"]
            if "0x" + topics[0].hex() == TOPIC_TRANSFER_EVENT:
                return log

    @staticmethod
    def _get_transaction_costs(tx_receipt: TxReceipt) -> Decimal:
        gas_used = int(tx_receipt["gasUsed"])
        effective_gas_price = int(tx_receipt["effectiveGasPrice"])
        l1_fee = int(tx_receipt["l1Fee"], 16)
        tx_cost_wei = gas_used * effective_gas_price + l1_fee
        return Decimal(Web3.from_wei(tx_cost_wei, "ether"))

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
