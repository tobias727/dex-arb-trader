import asyncio
from logging import Logger
from web3 import AsyncWeb3

from utils.web3_utils import connect_web3_async
from config import (
    UNISWAP_POOL_ID,
    TICK_BITMAP_HELPER_ADDRESS,
    TICK_BITMAP_HELPER_ABI,
    UNICHAIN_RPC_URL,
    ALCHEMY_API_KEY,
)


async def snapshot_once(feed, logger: Logger) -> None:
    """Initialize pool state."""
    w3 = connect_web3_async(UNICHAIN_RPC_URL + ALCHEMY_API_KEY)
    ticks_raw, snapshot_block = await initialize_uniswap_pool(w3)
    feed.create_snapshot(ticks_raw, snapshot_block)

    logger.warning("Initial snapshot applied at block %s", snapshot_block)


async def initialize_uniswap_pool(w3: AsyncWeb3):
    """
    Initialize Uniswap pool state by fetching data from the blockchain.
    Notice: no pending flag (flashblocks) is used -> returns flashblock index 0 state.
    """
    await asyncio.sleep(5)  # wait for feed warmup

    pool_id_bytes = bytes.fromhex(UNISWAP_POOL_ID.removeprefix("0x"))

    tick_bitmap_helper = w3.eth.contract(
        address=TICK_BITMAP_HELPER_ADDRESS, abi=TICK_BITMAP_HELPER_ABI
    )

    def _tick_to_word(tick: int) -> int:
        compressed = tick // tick_spacing
        if tick < 0 and tick % tick_spacing != 0:
            compressed -= 1
        return compressed >> 8

    # get block number for snapshot
    snapshot_block = await w3.eth.block_number

    tick_spacing = 10
    min_word = _tick_to_word(-887272)
    max_word = _tick_to_word(887272)

    # first call: get initialized tick bitmaps
    bitmaps = await tick_bitmap_helper.functions.getTickBitmapsRange(
        pool_id_bytes,
        min_word,
        max_word,
    ).call(block_identifier=snapshot_block)
    tick_indices: list[int] = []
    word_pos_indices = list(range(min_word, max_word + 1))
    for ind, bitmap in zip(word_pos_indices, bitmaps):
        if bitmap != 0:
            for i in range(256):
                bit = 1
                initialized = (bitmap & (bit << i)) != 0
                if initialized:
                    tick_index = (ind * 256 + i) * tick_spacing
                    tick_indices.append(tick_index)

    # second call: get tick data for initialized ticks
    ticks_raw = await tick_bitmap_helper.functions.getTicks(
        pool_id_bytes,
        tick_indices,
    ).call(block_identifier=snapshot_block)

    # ticks_raw : [(index, liquidityGross, liquidityNet, fee0, fee1), ...]
    return ticks_raw, snapshot_block
