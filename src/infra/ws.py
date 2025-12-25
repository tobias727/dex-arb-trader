import asyncio
import websockets
from feeds.flashblock_feed import UnichainFlashFeed
from feeds.binance_feed import BinanceDepthFeed


async def ws_reader(
    url, queue: asyncio.Queue, headers=None, ping_interval=None, ping_timeout=None
):
    """Pushes raw_msg from a WebSocket connection to the provided buffer."""
    async with websockets.connect(
        url,
        additional_headers=headers,
        max_queue=None,
        ping_interval=ping_interval,
        ping_timeout=ping_timeout,
    ) as ws:
        async for raw_msg in ws:
            await queue.put(raw_msg)


async def feed_loop(queue: asyncio.Queue, feed: UnichainFlashFeed | BinanceDepthFeed):
    """Passes new Flashblocks to feed"""
    while True:
        raw = await queue.get()
        feed.process(raw)
