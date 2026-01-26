from datetime import datetime
from logging import Logger
import asyncio
from typing import Callable, Awaitable
from decimal import Decimal
from web3.types import TxReceipt
from web3.datastructures import AttributeDict
from web3 import Web3

from clients.binance.client import BinanceClient
from clients.uniswap.client import UniswapClient
from state.balances import Balances
from state.flashblocks import FlashblockBuffer
from infra.monitoring import TelegramBot, append_row_to_csv
from config import (
    TOKEN1_DECIMALS,
    BINANCE_FEE,
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
        "fatal_error_future",
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
        fatal_error_future: asyncio.Future | None = None,
    ):
        self.balances = balances
        self.logger = logger
        self.fetch_balances = fetch_balances
        self.binance_client = binance_client
        self.uniswap_client = uniswap_client
        self.flashblock_buffer = flashblock_buffer
        self.telegram_bot = telegram_bot
        self.fatal_error_future = fatal_error_future
        self._exec_in_progress = False

    def execute_b_sell_u_buy(self, dy_in, detected_block: int, detected_fb_index: int):
        """Delegates execution given dy_in (USDC)"""
        if self._exec_in_progress:
            self.logger.warning(
                "Execution skipped: post_execute_hook still running (b_sell_u_buy, block #%s-%s)",
                detected_block,
                detected_fb_index,
            )
            return
        task = asyncio.create_task(
            self._guarded_execute(False, detected_block, detected_fb_index)
        )
        task.add_done_callback(self._handle_exec_task_done)

    def execute_b_buy_u_sell(self, dx_in, detected_block: int, detected_fb_index: int):
        """Delegates execution given dx_in (ETH)"""
        if self._exec_in_progress:
            self.logger.warning(
                "Execution skipped: post_execute_hook still running (b_buy_u_sell, block #%s-%s)",
                detected_block,
                detected_fb_index,
            )
            return
        task = asyncio.create_task(
            self._guarded_execute(True, detected_block, detected_fb_index)
        )
        task.add_done_callback(self._handle_exec_task_done)

    async def _guarded_execute(
        self, zero_for_one: bool, detected_block: int, detected_fb_index: int
    ) -> None:
        self._exec_in_progress = True
        await self._execute(zero_for_one, detected_block, detected_fb_index)
        self._exec_in_progress = False

    async def _execute(
        self, zero_for_one: bool, detected_block: int, detected_fb_index: int
    ) -> None:
        """Sequentially execute Uniswap/Binance legs"""
        # pre-execution hook
        if not self._pre_execute_hook(zero_for_one):
            return
        b_side = "BUY" if zero_for_one else "SELL"

        # 1. Uniswap via eth_sendBundle + wait/check if included
        u_bundle_hash = await self.uniswap_client.send_bundle(zero_for_one, 0.002)
        executed = await self._wait_for_own_tx(
            u_bundle_hash, 50
        )  # 50 flashblocks >= 10 blocks
        if not executed:
            # missed opp
            self.logger.warning("Tx not included: ")
            return
        self.uniswap_client.nonce += 1

        # 2. Binance only when bundle was included
        b_response = await self.binance_client.execute_trade(b_side, 0.002)

        # post-execution hook
        u_receipt = await asyncio.to_thread(
            self.uniswap_client.fetch_receipt, u_bundle_hash
        )
        await self._post_execute_hook(
            b_response, u_receipt, detected_block, detected_fb_index
        )

    async def _wait_for_own_tx(self, tx_hash: str, max_blocks: int) -> bool:
        """
        Subscriber to _new_block event in FlashblockBuffer
        Returns 'True' if tx was executed and found in the buffer
        """
        for _ in range(max_blocks):
            await self.flashblock_buffer.wait_for_new_block()
            if self.flashblock_buffer.lookup(tx_hash) is not None:
                return True
        return False

    async def _post_execute_hook(
        self,
        b_response: dict,
        u_receipt: TxReceipt,
        detected_block: int,
        detected_fb_index: int,
    ) -> None:
        """Refreshes balances"""
        tx_hash_raw = u_receipt.get("transactionHash")
        tx_hash = "0x" + tx_hash_raw.hex()

        block_number = None
        index = None

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
        all_tx_hashes_in_fb = self.flashblock_buffer.get_tx_hashes(block_number, index)
        append_row_to_csv(
            "executions.csv",
            {
                "detected_block": detected_block,
                "detected_fb_index": detected_fb_index,
                "block": block_number,
                "fb_index": index,
                "pnl": pnl,
                "tx_hashes": all_tx_hashes_in_fb,
                "b_side": b_response.get("side"),
                "u_tx_hash": tx_hash,
            },
        )
        await self.telegram_bot.notify_executed(pnl)
        await self.fetch_balances()

    def _pre_execute_hook(self, zero_for_one: bool) -> bool:
        """Checks balances"""
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
        return True

    def _handle_exec_task_done(self, task: asyncio.Task):
        exc = task.exception()
        if exc:
            self.logger.error("Error during execution", exc_info=exc)
            self.fatal_error_future.set_exception(exc)

    @staticmethod
    def _current_ms_of_second() -> int:
        now = datetime.now()
        return now.microsecond // 1000

    @staticmethod
    def calculate_pnl(response_binance: dict, receipt_uniswap: TxReceipt) -> Decimal:
        """Returns PnL in USDC"""
        fill_price, qty = Executor._acc_fills(response_binance["fills"])
        notional_price = fill_price * qty
        b_fee = notional_price * BINANCE_FEE
        transfer_out_amount = Executor._get_transfer_amount(receipt_uniswap)
        u_fee_in_eth = Executor._get_transaction_costs(receipt_uniswap)
        if response_binance["side"] == "SELL":
            sell = notional_price
            buy = transfer_out_amount
        else:  # Binance Side == "BUY":
            sell = transfer_out_amount
            buy = notional_price
        u_fee = u_fee_in_eth * fill_price
        total_fees = b_fee + u_fee
        return sell - (buy + total_fees)

    @staticmethod
    def _acc_fills(fills: dict) -> tuple[Decimal, Decimal, Decimal]:
        total_notional = Decimal("0")
        total_qty = Decimal("0")
        for fill in fills:
            price = Decimal(fill["price"])
            qty = Decimal(fill["qty"])
            total_notional += price * qty
            total_qty += qty
        avg_price = total_notional / total_qty
        return avg_price, total_qty

    @staticmethod
    def _get_transfer_amount(tx_receipt: TxReceipt) -> Decimal:
        transfer_topic_log = Executor._extract_transfer_log(tx_receipt)
        transfer_out_raw = int(transfer_topic_log.data.hex(), 16)
        return transfer_out_raw / Decimal(f"1e{TOKEN1_DECIMALS}")

    @staticmethod
    def _extract_transfer_log(tx_receipt: TxReceipt) -> AttributeDict | None:
        for log in tx_receipt["logs"]:
            topics = log["topics"]
            # TOPIC_TRANSFER_EVENT
            if (
                "0x" + topics[0].hex()
                == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            ):
                return log

    @staticmethod
    def _get_transaction_costs(tx_receipt: TxReceipt) -> Decimal:
        gas_used = int(tx_receipt["gasUsed"])
        effective_gas_price = int(tx_receipt["effectiveGasPrice"])
        l1_fee = int(tx_receipt["l1Fee"], 16)
        tx_cost_wei = gas_used * effective_gas_price + l1_fee
        return Decimal(Web3.from_wei(tx_cost_wei, "ether"))
