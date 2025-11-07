import json
import sys
import asyncio
import time
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
        self.last_trade_result = {"response_binance": {}, "receipt_uniswap": {}}
        self.ws = None
        self.balance_update_task = None
        self.exec_sign_task = None
        self.new_block_ts = None
        self.u_executed_latency = None
        self.b_perf_counter = None
        self.block_processing_paused = False


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
        self.request_balance_update()
        self.request_exec_signing()
        try:
            async with asyncio.TaskGroup() as tg:
                _task1 = tg.create_task(self.listen_uniswap())
                _task2 = tg.create_task(self.listen_binance())
                _task3 = tg.create_task(monitor_ip_change(self.logger))
        finally:
            # manual session for faster requests
            await self.binance_client.close()

    async def listen_uniswap(self):
        """Uniswap listener with Flashblocks as pending enabled"""
        try:
            async with websockets.connect(
                self.uniswap_client.state.url_ws
            ) as self.state.ws:
                sub_req = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": ["newHeads"],
                }
                self.logger.info("------------------")
                await self.state.ws.send(json.dumps(sub_req))
                while True:
                    msg = await self.state.ws.recv()
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
                        self.state.new_block_ts = time.perf_counter()
                        print("DEBUG: NEW Block")
                        await self.uniswap_client.on_new_block(self.state.ws)
                    # Bid
                    elif msg_obj.get("id") == 42:
                        bid_latency = time.perf_counter() - self.state.new_block_ts
                        amount_out, gas = (
                            await self.uniswap_client.decode_uniswap_quote(
                                msg_obj.get("result")
                            )
                        )
                        self.state.quotes["bid"] = (amount_out, gas)
                        print("DEBUG: %s", amount_out)
                    # Ask
                    elif msg_obj.get("id") == 43:
                        ask_latency = time.perf_counter() - self.state.new_block_ts
                        amount_in, gas = await self.uniswap_client.decode_uniswap_quote(
                            msg_obj.get("result")
                        )
                        self.state.quotes["ask"] = (amount_in, gas)
                        print("DEBUG: %s", amount_in)
                    # Executed
                    elif msg_obj.get("id") == 61:
                        self.state.u_executed_latency = (
                            time.perf_counter() - self.state.new_block_ts
                        )
                        self.request_exec_signing()
                        self.state.last_trade_result["receipt_uniswap"] = (
                            await self.uniswap_client.get_trade_result(
                                msg_obj.get("result")
                            )
                        )
                        if self.state.last_trade_result["response_binance"] is not None:
                            await self.process_trade_result()
                    else:
                        self.logger.warning("Unknown msg: %s", msg)

                    if (
                        "bid" in self.state.quotes
                        and "ask" in self.state.quotes
                        and self.state.orderbook
                    ):
                        await self.detect()
                        self.logger.info(
                            "Quotes: b_bid=%s, b_ask=%s, u_bid=%s, u_ask=%s | new_block_ts=%.4fs, u_bid_latency=%.4fs, u_ask_latency=%.4fs",
                            self.state.orderbook["b"],
                            self.state.orderbook["a"],
                            self.state.quotes["bid"][0],
                            self.state.quotes["ask"][0],
                            self.state.new_block_ts,
                            # pylint: disable=used-before-assignment.
                            bid_latency,
                            ask_latency,
                        )
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
        print("DEBUG2: ", edge)
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

    async def execute(self, side):
        """Execute trade"""
        task1 = None
        if side == "CEX_buy_DEX_sell":
            async with asyncio.TaskGroup() as tg:
                task1 = tg.create_task(self.binance_client.execute_trade("BUY"))
                _task2 = tg.create_task(
                    self.uniswap_client.execute_trade("SELL", self.state.ws)
                )
        elif side == "CEX_sell_DEX_buy":
            async with asyncio.TaskGroup() as tg:
                task1 = tg.create_task(self.binance_client.execute_trade("SELL"))
                _task2 = tg.create_task(
                    self.uniswap_client.execute_trade("BUY", self.state.ws)
                )
        self.state.last_trade_result["response_binance"], self.state.b_perf_counter = (
            task1.result()
        )
        if self.state.last_trade_result["receipt_uniswap"] is not None:
            await self.process_trade_result()
        self.request_balance_update()

    async def process_trade_result(self):
        """Calculates PnL, saves to csv and notifies telegram bot"""
        pnl = calculate_pnl(
            self.state.last_trade_result["response_binance"],
            self.state.last_trade_result["receipt_uniswap"],
        )
        b_executed_latency = self.state.b_perf_counter - self.state.new_block_ts
        self.logger.info(
            "Executed: pnl=%s, u_executed_latency=%s, b_executed_latency=%s",
            pnl,
            self.state.u_executed_latency,
            b_executed_latency,
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
            b_usdc > TOKEN0_INPUT * 4_500 and u_eth > (TOKEN0_INPUT + GAS_RESERVE)
        )
        self.state.tradeable_sides["CEX_sell_DEX_buy"] = (
            b_eth > TOKEN0_INPUT and u_usdc > TOKEN0_INPUT * 4_500
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
