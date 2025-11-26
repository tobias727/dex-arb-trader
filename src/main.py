import json
import sys
import asyncio
import time
from collections import deque
import brotli
import websockets
from src.clients.binance_client import BinanceClient
from src.clients.uniswap_client import UniswapV4Client
from src.utils.utils import (
    calculate_pnl,
    monitor_ip_change,
    append_trade_to_csv,
    setup_logger,
)
from src.utils.telegram_bot import TelegramBot
from src.utils.exceptions import ExecutionError
from src.config import (
    TOKEN0_INPUT,
    MIN_EDGE,
    TESTNET,
    GAS_RESERVE,
    BINANCE_FEE,
    TOKEN1_DECIMALS,
    BINANCE_BASE_URL_WS,
)


# pylint: disable=too-many-instance-attributes, too-few-public-methods
class State:
    """Runtime state container for DexArbTrader."""

    def __init__(self):
        self.orderbook = {}
        self.quotes = {}
        self.balances = {
            "binance": {"ETH": None, "USDC": None},
            "uniswap": {"ETH": None, "USDC": None},
        }
        self.tradeable_sides = {"CEX_buy_DEX_sell": False, "CEX_sell_DEX_buy": False}
        self.last_trade_result = {"response_binance": None, "receipt_uniswap": None}
        self.balance_update_task = None
        self.exec_sign_task = None
        self.new_block_ts = None
        self.opportunity_detected_ts = None
        self.block_processing_paused = False
        self.current_block_number_head = None
        self.bid_latency = None
        self.ask_latency = None
        self.bid_latency_server = None
        self.ask_latency_server = None
        self.last_blocks = deque(maxlen=10)


class DexArbTrader:
    """Core logic for async trader"""

    def __init__(self):
        self.logger = setup_logger()
        self.binance_client = BinanceClient(self.logger)
        self.uniswap_client = UniswapV4Client(self.logger)
        self.telegram_bot = TelegramBot()
        self.state = State()

    async def run(self):
        """Entrypoint"""
        await self.binance_client.init_session()
        await self.uniswap_client.init_session()
        self.request_balance_update()
        self.request_exec_signing()
        try:
            async with asyncio.TaskGroup() as tg:
                _task1 = tg.create_task(self.listen_uniswap())
                _task2 = tg.create_task(self.listen_flashblocks())
                _task3 = tg.create_task(self.listen_binance())
                _task4 = tg.create_task(monitor_ip_change(self.logger))
        finally:
            await self.binance_client.close()
            await self.uniswap_client.close()

    async def listen_flashblocks(self):
        """Flashblock listener to analyze latency"""
        async with websockets.connect(self.uniswap_client.state.flashblock_ws) as ws:
            async for message in ws:
                payload = json.loads(brotli.decompress(message))
                flashblock_position = payload.get("index") + 1
                tx_hashes = payload.get("metadata", {}).get("receipts", {}).keys()
                block_number = payload.get("metadata", {}).get("block_number")
                self.state.last_blocks.append(
                    {
                        "block_number": block_number,
                        "flashblock_position": flashblock_position,
                        "transactions": tx_hashes,
                    }
                )

    async def listen_uniswap(self):
        """Uniswap listener with Flashblocks as pending enabled"""
        try:
            async with websockets.connect(
                self.uniswap_client.state.url_ws, ping_interval=20, ping_timeout=20
            ) as ws:
                sub_req = {
                    "jsonrpc": "2.0",
                    "method": "eth_subscribe",
                    "params": ["newHeads"],
                }
                await ws.send(json.dumps(sub_req))
                while True:
                    msg = await ws.recv()
                    msg_obj = json.loads(msg)
                    if self.state.block_processing_paused:
                        if (
                            self.state.balance_update_task is None
                            or self.state.balance_update_task.done()
                        ) and (
                            self.state.exec_sign_task is None
                            or self.state.exec_sign_task.done()
                        ):
                            self.state.block_processing_paused = False
                        else:
                            continue
                    # new block event
                    if msg_obj.get("method") == "eth_subscription":
                        self.state.quotes.clear()
                        self.state.new_block_ts = time.time()
                        self.state.current_block_number_head = int(
                            msg_obj["params"]["result"]["number"], 16
                        )
                        await self.uniswap_client.on_new_block(ws)
                    # Bid
                    elif msg_obj.get("id") == 42:
                        self.state.bid_latency = time.time() - self.state.new_block_ts
                        amount_out, gas = (
                            await self.uniswap_client.decode_uniswap_quote(
                                msg_obj.get("result")
                            )
                        )
                        self.state.quotes["bid"] = (amount_out, gas)
                    # Ask
                    elif msg_obj.get("id") == 43:
                        self.state.ask_latency = time.time() - self.state.new_block_ts
                        amount_in, gas = await self.uniswap_client.decode_uniswap_quote(
                            msg_obj.get("result")
                        )
                        self.state.quotes["ask"] = (amount_in, gas)
                    elif msg_obj.get("id") is None and "result" in msg_obj:
                        self.logger.debug(
                            "Started eth_subscription with id '%s'",
                            msg_obj.get("result"),
                        )
                    else:
                        self.logger.warning("Unknown msg: %s", msg)

                    if (
                        "bid" in self.state.quotes
                        and "ask" in self.state.quotes
                        and self.state.orderbook
                    ):
                        await self.detect()
                        self.state.quotes.clear()
        except Exception as e:
            await self.telegram_bot.notify_crashed(e)
            self.logger.error("Bot crashed: %s", e)
            sys.exit(1)

    async def listen_binance(self):
        """Binance listener, top of book only"""
        binance_uri = f"{BINANCE_BASE_URL_WS}/ws/ethusdc@bookTicker"
        async with websockets.connect(binance_uri) as ws:
            while True:
                msg = await ws.recv()
                await self.update_order_book(msg)

    async def update_order_book(self, msg):
        """Updates local order book"""
        data = json.loads(msg)
        self.state.orderbook.update(data)

    async def detect(self):
        """Edge detector, calls execute"""
        self.state.opportunity_detected_ts = time.time()
        adj_b_bid = int(
            float(self.state.orderbook["b"])
            * 10**TOKEN1_DECIMALS
            * float(TOKEN0_INPUT)
            * (1 - BINANCE_FEE)
        )  # bid * input * (1-fee) * 10^6
        adj_b_ask = int(
            float(self.state.orderbook["a"])
            * 10**TOKEN1_DECIMALS
            * float(TOKEN0_INPUT)
            * (1 + BINANCE_FEE)
        )  # ask * input * (1+fee) * 10^6
        adj_u_bid = self.state.quotes["bid"][0]  # ignore gas for now
        adj_u_ask = self.state.quotes["ask"][0]  # ignore gas for now
        edge = adj_u_bid - adj_b_ask
        # CEX_buy_DEX_sell
        if edge > MIN_EDGE and self.state.tradeable_sides["CEX_buy_DEX_sell"]:
            await self.execute("CEX_buy_DEX_sell")
        elif edge > 0:
            self.logger.warning("Detected: CEX_buy_DEX_sell, %s", f"{edge:_}")
        # CEX_sell_DEX_buy
        edge = adj_b_bid - adj_u_ask
        if edge > MIN_EDGE and self.state.tradeable_sides["CEX_sell_DEX_buy"]:
            await self.execute("CEX_sell_DEX_buy")
        elif edge > 0:
            self.logger.warning("Detected: CEX_sell_DEX_buy, %s", f"{edge:_}")
        self.logger.info(
            "#%s\n"
            "                               Binance b: %10s | a: %10s\n"
            "                               Uniswap b: %10s | a: %10s [b: %.1fms, a: %.1fms]",
            self.state.current_block_number_head,
            f"{adj_b_bid:_}",
            f"{adj_b_ask:_}",
            f"{adj_u_bid:_}",
            f"{adj_u_ask:_}",
            self.state.bid_latency * 1000,
            self.state.ask_latency * 1000,
        )

    async def execute(self, side):
        """Execute trade"""
        task1 = None
        task2 = None
        if side == "CEX_buy_DEX_sell":
            async with asyncio.TaskGroup() as tg:
                task1 = tg.create_task(self.binance_client.execute_trade("BUY"))
                task2 = tg.create_task(self.uniswap_client.execute_trade("SELL"))
        elif side == "CEX_sell_DEX_buy":
            async with asyncio.TaskGroup() as tg:
                task1 = tg.create_task(self.binance_client.execute_trade("SELL"))
                task2 = tg.create_task(self.uniswap_client.execute_trade("BUY"))
        self.state.last_trade_result["response_binance"] = task1.result()
        self.state.last_trade_result["receipt_uniswap"] = task2.result()
        # pylint: disable=no-member
        if self.state.last_trade_result["receipt_uniswap"].status != 1:
            raise ExecutionError
        await self.process_trade_result()
        self.request_exec_signing()
        self.request_balance_update()

    async def process_trade_result(self):
        """Calculates PnL, saves to csv and notifies telegram bot"""
        pnl = calculate_pnl(
            self.state.last_trade_result["response_binance"],
            self.state.last_trade_result["receipt_uniswap"],
        )
        block, flashblock = await self.find_trade_in_flashblocks()
        if block:
            u_executed_latency = int(block) - (
                int(self.state.current_block_number_head) + 1
            )
        else:
            u_executed_latency, flashblock = "None", "None"
        b_executed_latency = self.state.last_trade_result["response_binance"][
            "transactTime"
        ] - (self.state.opportunity_detected_ts * 1000)
        self.logger.info(
            "Executed: pnl=%s\n"
            "                               Uniswap:  %sB, %sf, 0x%s\n"
            "                               Binance:  %.1fms, %s",
            pnl,
            u_executed_latency,
            flashblock,
            self.state.last_trade_result["receipt_uniswap"]["transactionHash"].hex(),
            b_executed_latency,
            self.state.last_trade_result["response_binance"]["fills"],
        )
        await self.telegram_bot.notify_executed(pnl)
        append_trade_to_csv(
            "trades.csv" if TESTNET else "trades_LIVE.csv",
            {
                "response_binance": self.state.last_trade_result["response_binance"],
                "receipt_uniswap": self.state.last_trade_result["receipt_uniswap"],
                "binance_side": self.state.last_trade_result["response_binance"][
                    "side"
                ],
                "pnl": pnl,
            },
        )
        self.state.last_trade_result = {"response_binance": {}, "receipt_uniswap": {}}

    async def find_trade_in_flashblocks(self):
        """Searches the flashblock position in the executed block"""
        tx_hash = (
            "0x"
            + self.state.last_trade_result["receipt_uniswap"]["transactionHash"].hex()
        )
        await asyncio.sleep(0.2)
        for entry in self.state.last_blocks:
            for tx in entry["transactions"]:
                if tx == tx_hash:
                    return entry["block_number"], entry["flashblock_position"]
        return None, None

    def request_balance_update(self):
        """Starts update_balances and blocks processing until refreshed"""
        self.state.block_processing_paused = True
        if not self.state.balance_update_task or self.state.balance_update_task.done():
            self.state.balance_update_task = asyncio.create_task(self.update_balances())

    def request_exec_signing(self):
        """Starts async task for encode+sign and blocks processing until done."""
        self.state.block_processing_paused = True
        if not self.state.exec_sign_task or self.state.exec_sign_task.done():
            self.state.exec_sign_task = asyncio.create_task(
                self.update_uniswap_exec_signed_tx()
            )

    async def update_uniswap_exec_signed_tx(self):
        """Updates pre-signed tx with current nonce"""
        self.uniswap_client.state.signed_raw_tx_buy = (
            self.uniswap_client.encode_and_sign_exec_tx(zero_for_one=False)
        )
        self.uniswap_client.state.signed_raw_tx_sell = (
            self.uniswap_client.encode_and_sign_exec_tx(zero_for_one=True)
        )

    async def update_balances(self):
        """Updates self.state.balances"""
        b_eth, b_usdc = await self.binance_client.get_balances()
        u_eth, u_usdc = await self.uniswap_client.get_balances()
        self.state.balances["binance"] = {"ETH": b_eth, "USDC": b_usdc}
        self.state.balances["uniswap"] = {"ETH": u_eth, "USDC": u_usdc}
        # TODO: 4_500 price
        self.state.tradeable_sides["CEX_buy_DEX_sell"] = (
            b_usdc > TOKEN0_INPUT * 3_000 and u_eth > (TOKEN0_INPUT + GAS_RESERVE)
        )
        self.state.tradeable_sides["CEX_sell_DEX_buy"] = (
            b_eth > TOKEN0_INPUT and u_usdc > TOKEN0_INPUT * 3_000
        )
        self.logger.info(
            "Balances: b_eth=%s, b_usdc=%s, u_eth=%s, u_usdc=%s",
            b_eth,
            b_usdc,
            u_eth,
            u_usdc,
        )


if __name__ == "__main__":
    bot = DexArbTrader()
    asyncio.run(bot.run())
