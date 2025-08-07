from typing import List


class V2Params:
    """Struct for v2 params"""

    def __init__(
        self,
        token0: str,
        token1: str,
        token0_amounts: List[float],
    ):
        self.token0 = token0
        self.token1 = token1
        self.token0_amounts = token0_amounts


class V4Params:
    """Struct for v4 params"""

    def __init__(
        self,
        token_in: str,
        token_out: str,
        amounts_in: list[float],
        pool_fee: int,
        pool_tick_spacing: int,
        pool_hooks: str = "0x0000000000000000000000000000000000000000",
    ):
        self.token_in = token_in
        self.token_out = token_out
        self.amounts_in = amounts_in
        self.pool_fee = pool_fee
        self.pool_tick_spacing = pool_tick_spacing
        self.pool_hooks = pool_hooks
