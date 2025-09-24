from src.binance.rpc_client import BinanceClientRpc
from src.unichain.clients.v4client import UnichainV4Client


class Orchestrator:
    """Responsible for executing two-leg trade"""

    def __init__(self, logger):
        self.logger = logger
        self.side_mapping = {
            "CEX_buy_DEX_sell": ("BUY", "SELL"),
            "CEX_sell_DEX_buy": ("SELL", "BUY"),
        }

    def execute(self, side: str, binance: BinanceClientRpc, uniswap: UnichainV4Client):
        """
        Executes first CEX, then DEX for minimal slippage
        """
        try:
            binance_side, uniswap_side = self.side_mapping[side]
        except KeyError:
            raise ValueError(f"Invalid side value: {side}")

        # place CEX leg first
        response_binance = binance.execute_trade(binance_side)
        if response_binance["status"] != "FILLED":
            self.logger.warning("Unexpected Binance status: %s", response_binance)
            raise RuntimeError("Binance leg failed")

        # place DEX leg second
        receipt_uniswap = uniswap.execute_trade(uniswap_side)
        if receipt_uniswap.status != 1:
            self.logger.warning("Unexpected Uniswap receipt: %s", receipt_uniswap)
            raise RuntimeError("Uniswap leg failed")

        return response_binance, receipt_uniswap
