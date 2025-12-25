from typing import Dict
from dataclasses import dataclass, field


@dataclass(slots=True)
class Tick:
    """Holds the liquidity state of a Unichain pool tick."""

    liquidity_gross: int
    liquidity_net: int


@dataclass(slots=True)
class Pool:
    """Holds the state of a Unichain liquidity pool."""

    sqrt_price_x96: int | None = None
    price: float | None = None
    active_liquidity: int | None = None
    current_tick: int | None = None
    ticks: Dict[int, Tick] = field(default_factory=dict)

    def load_ticks(self, ticks_raw):
        """Loads tick for pool"""
        self.ticks = {
            int(idx): Tick(
                liquidity_gross=int(liq_gross),
                liquidity_net=int(liq_net),
            )
            for (idx, liq_gross, liq_net, _fee0, _fee1) in ticks_raw
        }
