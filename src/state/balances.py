from dataclasses import dataclass


@dataclass(slots=True)
class Balances:
    """Holds the state for account balances"""

    b_eth: float | None = None
    b_usdc: float | None = None
    u_eth: float | None = None
    u_usdc: float | None = None
