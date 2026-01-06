import asyncio
import logging

from utils.telegram_bot import TelegramBot
from utils.utils import monitor_ip_change
from utils.initialize_uniswap_pool import snapshot_once
from clients.binance_client import BinanceClient
from clients.uniswap_client import UniswapClient
from feeds.flashblock_feed import UnichainFlashFeed
from feeds.binance_feed import BinanceDepthFeed
from infra.ws import ws_reader, feed_loop
from state.orderbook import OrderBook
from state.pool import Pool
from state.balances import Balances
from state.flashblocks import FlashblockBuffer
from engine.detector import ArbDetector
from engine.executor import Executor
from config import (
    UNICHAIN_FLASHBLOCKS_WS_URL,
    BINANCE_URI_SBE,
    BINANCE_API_KEY_ED25519,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger()


async def fetch_balances(
    balances: Balances, binance_client: BinanceClient, uniswap_client: UniswapClient
):
    """Updates balances"""
    balances.b_eth, balances.b_usdc = await binance_client.get_balances()
    balances.u_eth, balances.u_usdc = uniswap_client.get_balances()
    logger.info(
        "Balances: b_eth=%s, b_usdc=%s, u_eth=%s, u_usdc=%s",
        balances.b_eth,
        balances.b_usdc,
        balances.u_eth,
        balances.u_usdc,
    )


async def main(telegram_bot: TelegramBot):
    """Entrypoint"""
    # state
    pool = Pool()
    orderbook = OrderBook()
    balances = Balances()
    flashblock_buffer = FlashblockBuffer()

    # clients
    binance_client = BinanceClient()
    uniswap_client = UniswapClient()

    # engine
    executor = Executor(
        balances,
        logger,
        lambda: fetch_balances(balances, binance_client, uniswap_client),
        binance_client,
        uniswap_client,
        flashblock_buffer,
        telegram_bot,
    )
    detector = ArbDetector(pool, orderbook, executor, logger)

    # feeds
    u_queue = asyncio.Queue(maxsize=1024)
    u_feed = UnichainFlashFeed(
        pool, logger, detector.on_flashblock_done, flashblock_buffer
    )
    b_queue = asyncio.Queue(maxsize=1024)
    b_feed = BinanceDepthFeed(orderbook, logger)
    b_url = f"{BINANCE_URI_SBE}/ws/ethusdc@bestBidAsk"
    b_headers = [("X-MBX-APIKEY", BINANCE_API_KEY_ED25519)]

    await asyncio.gather(
        fetch_balances(balances, binance_client, uniswap_client),
        # Unichain
        ws_reader(UNICHAIN_FLASHBLOCKS_WS_URL, u_queue),
        feed_loop(u_queue, u_feed),
        snapshot_once(u_feed, logger),
        uniswap_client.keep_connection_hot(ping_interval=30),
        # Binance
        ws_reader(b_url, b_queue, headers=b_headers, ping_interval=20, ping_timeout=60),
        feed_loop(b_queue, b_feed),
        binance_client.keep_connection_hot(ping_interval=30),
        monitor_ip_change(logger),
    )


async def entry():
    """Initializes telegram bot and runs main with error handling"""
    telegram_bot = TelegramBot()
    try:
        await main(telegram_bot)
    except Exception as e:
        await telegram_bot.notify_crashed(e)
        raise


if __name__ == "__main__":
    asyncio.run(entry())
