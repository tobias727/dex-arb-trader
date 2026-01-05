import asyncio
import orjson
import brotli
from eth_abi import decode as abi_decode

from config import (
    UNICHAIN_POOL_MANAGER,
    UNISWAP_POOL_ID,
)
from utils.initialize_uniswap_pool import snapshot_once
from state.pool import Pool, Tick
from state.flashblocks import FlashblockBuffer
from engine.detector import ArbDetector

SWAP_TOPIC = "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
MODIFY_LIQ_TOPIC = "0xf208f4912782fd25c7f114ca3723a2d5dd6f3bcc3ac8db5af63baa85f711d5ec"
DONATE_TOPIC = "0x29ef05caaff9404b7cb6d1c0e9bbae9eaa7ab2541feba1a9c4248594c08156cb"

pool_manager = UNICHAIN_POOL_MANAGER.lower()
pool_id = UNISWAP_POOL_ID.lower()

# sqrt_price_x96
Q96 = 2**96
DEC0 = 18  # ETH
DEC1 = 6  # USDC
SCALE = 10 ** (DEC0 - DEC1)


class UnichainFlashFeed:
    """Processes Unichain flashblock feed messages and updates pool state"""

    __slots__ = (
        "pool",
        "logger",
        "snapshot_block_number",
        "have_snapshot",
        "buffer",
        "last_block",
        "last_flashblock_index",
        "on_flashblock_done",
        "flashblock_buffer",
    )

    def __init__(
        self,
        pool: Pool,
        logger,
        on_flashblock_done: ArbDetector.on_flashblock_done,
        flashblock_buffer: FlashblockBuffer,
    ):
        self.pool = pool
        self.logger = logger
        self.on_flashblock_done = on_flashblock_done
        self.flashblock_buffer = flashblock_buffer

        self.snapshot_block_number: int | None = None
        self.buffer: list[tuple] = []
        self.last_block: int | None = None
        self.last_flashblock_index: int | None = None

    def create_snapshot(self, ticks_raw, snapshot_block_number):
        """Loads snapshot + set block number"""
        self.pool.load_ticks(ticks_raw)
        self.set_snapshot_block(snapshot_block_number)

    def set_snapshot_block(self, block_number: int):
        """Sets the snapshot block number and flushes any buffered messages."""
        self.snapshot_block_number = block_number
        self._flush_buffer()

    def _flush_buffer(self):
        """Filters events after snapshot block and applies them."""
        for block_number, index, payload in self.buffer:
            if block_number > self.snapshot_block_number:
                self._process_block(payload, block_number, index)
        self.buffer.clear()

    def process(self, raw_msg: bytes) -> None:
        """Process a raw message from main.feed_loop"""
        raw = brotli.decompress(raw_msg)
        payload = orjson.loads(raw)

        block_number = payload.get("metadata", {}).get("block_number", None)
        index = payload.get("index", None)
        self._check_for_gap(block_number, index)

        if self.snapshot_block_number is None:
            self.buffer.append((block_number, index, payload))
            return
        self._process_block(payload, block_number, index)

    def _process_block(self, payload, block_number, index) -> None:
        """Filters a block's transactions and applies relevant events."""
        receipts = payload.get("metadata", {}).get("receipts", {})
        if not receipts:
            return
        tx_hashes: list[str] = []
        for tx_hash, receipt in receipts.items():
            _tx_type, tx_data = next(iter(receipt.items()))
            if tx_data.get("status") != "0x1":
                continue
            tx_hashes.append("0x" + tx_hash.hex())
            logs = tx_data.get("logs", [])
            if not logs:
                continue
            for log in logs:
                address = log.get("address", "").lower()
                if address != pool_manager:
                    continue
                data = log.get("data", "")
                topics = log.get("topics", [])
                self._process_event(data, topics)
        if tx_hashes:
            self.flashblock_buffer.add_block(block_number, index, tx_hashes)
        self.on_flashblock_done(block_number, index)

    def _process_event(self, data: tuple, topics: list) -> None:
        """Applies a single event to the pool state."""
        if topics[0] == SWAP_TOPIC and topics[1] == pool_id:
            # SWAP event
            _amount0, _amount1, sqrt_price_x96, liquidity, tick, _fee = (
                self.decode_swap(data)
            )
            self._process_swap_event(sqrt_price_x96, liquidity, tick)

        elif topics[0] == MODIFY_LIQ_TOPIC and topics[1] == pool_id:
            # MODIFY_LIQUIDITY event
            tick_lower, tick_upper, liq_delta, _salt = self.decode_modify_liquidity(
                data
            )
            self._process_modify_liquidity_event(tick_lower, tick_upper, liq_delta)

        elif topics[0] == DONATE_TOPIC and topics[1] == pool_id:
            # DONATE event
            self.logger.warning("DONATE event - not implemented")
            # not implemented, resync state
            self.request_resync()

    def _process_swap_event(self, sqrt_price_x96, liquidity, tick):
        """Updates pool state after Swap event"""
        pool = self.pool

        pool.sqrt_price_x96 = int(sqrt_price_x96)
        pool.active_liquidity = int(liquidity)
        pool.current_tick = int(tick)

        # readable price
        sqrtP = pool.sqrt_price_x96 / Q96
        raw_price = sqrtP * sqrtP
        pool.price = raw_price * SCALE

    def _process_modify_liquidity_event(self, tick_lower, tick_upper, liq_delta):
        """Updates pool state for ModifyLiquidity event"""
        liq_delta = int(liq_delta)
        if liq_delta == 0:
            return

        tick_lower = int(tick_lower)
        tick_upper = int(tick_upper)
        delta_abs = abs(liq_delta)
        ticks = self.pool.ticks

        def get_or_create_tick(idx: int) -> Tick:
            t = ticks.get(idx)
            if t is None:
                t = Tick(liquidity_gross=0, liquidity_net=0)
                ticks[idx] = t
            return t

        lower_tick = get_or_create_tick(tick_lower)
        upper_tick = get_or_create_tick(tick_upper)

        # Update lower tick: +|ΔL| gross, +ΔL net
        lower_tick.liquidity_gross += delta_abs
        lower_tick.liquidity_net += liq_delta

        # Update upper tick: +|ΔL| gross, -ΔL net
        upper_tick.liquidity_gross += delta_abs
        upper_tick.liquidity_net -= liq_delta

        if lower_tick.liquidity_gross == 0:
            del ticks[tick_lower]

        if upper_tick.liquidity_gross == 0 and tick_upper in ticks:
            del ticks[tick_upper]

    def _check_for_gap(self, block_number: int, index: int) -> None:
        """Checks for gaps in block numbers and flashblock indices."""
        if self.last_flashblock_index is None:
            self.last_flashblock_index = index
            return

        # 0 = new block, 1-4 = flashblocks
        if index != 0:
            if index != self.last_flashblock_index + 1:
                self.logger.warning(
                    "Flashblock index jump detected: last %s, current %s",
                    self.last_flashblock_index,
                    index,
                )
                self.request_resync()
                return
        self.last_flashblock_index = index

        # 0 = new block
        if index != 0:
            return
        if self.last_block is None:
            self.last_block = block_number
            return
        if block_number != self.last_block + 1:
            self.logger.warning(
                "Block number jump detected: last %s, current %s",
                self.last_block,
                block_number,
            )
            self.request_resync()
            return
        self.last_block = block_number

    def request_resync(self):
        """Request new snapshot"""
        self.snapshot_block_number = None
        self.logger.warning("Detected diverging local state, resyncing...")
        asyncio.create_task(snapshot_once(self, self.logger))

    @staticmethod
    def decode_swap(data_hex: str):
        """Decode Swap event data."""
        data_bytes = bytes.fromhex(data_hex[2:])
        return abi_decode(
            [
                "int128",  # amount0
                "int128",  # amount1
                "uint160",  # sqrtPriceX96
                "uint128",  # liquidity
                "int24",  # tick
                "int24",  # fee
            ],
            data_bytes,
        )

    @staticmethod
    def decode_modify_liquidity(data_hex: str):
        """Decode ModifyLiquidity event data"""
        data_bytes = bytes.fromhex(data_hex[2:])  # strip '0x'
        return abi_decode(
            [
                "int24",  # tickLower
                "int24",  # tickUpper
                "int256",  # liquidityDelta
                "bytes32",  # salt
            ],
            data_bytes,
        )
