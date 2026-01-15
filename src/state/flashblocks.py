import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Tuple, Optional


@dataclass(slots=True)
class Flashblock:
    """Holds a flashblock state"""

    block_number: int
    index: int
    tx_hashes: List[str]


class FlashblockBuffer:
    """Holds recent flashblocks in memory and allows lookup by tx_hash"""

    __slots__ = ("_blocks", "_by_tx", "_new_block")

    def __init__(self, size: int = 20):
        self._blocks: Deque[Flashblock] = deque(maxlen=size)
        self._by_tx: Dict[str, Tuple[int, int]] = {}
        self._new_block: asyncio.Event = asyncio.Event()

    def add_block(self, block_number: int, index: int, tx_hashes: List[str]) -> None:
        """Adds block and remove oldest entry"""
        if len(self._blocks) == self._blocks.maxlen:
            oldest = self._blocks[0]
            for h in oldest.tx_hashes:
                self._by_tx.pop(h, None)

        flashblock = Flashblock(block_number, index, tx_hashes)
        self._blocks.append(flashblock)

        for h in tx_hashes:
            self._by_tx[h] = (block_number, index)

        # publisher
        self._new_block.set()

    def lookup(self, tx_hash: str) -> Optional[Tuple[int, int]]:
        """Returns (block_number, index) for given tx_hash"""
        return self._by_tx.get(tx_hash)

    async def wait_for_new_block(self) -> None:
        """Returns when new block"""
        await self._new_block.wait()
        self._new_block.clear()
