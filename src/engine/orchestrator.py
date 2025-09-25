import time
from src.binance.rpc_client import BinanceClientRpc
from src.unichain.clients.v4client import UnichainV4Client
from src.utils.utils import elapsed_ms


class Orchestrator:
    """Responsible for executing two-leg trade"""

    def __init__(self, logger):
        self.logger = logger
        self.side_mapping = {
            "CEX_buy_DEX_sell": ("BUY", "SELL"),
            "CEX_sell_DEX_buy": ("SELL", "BUY"),
        }

    def execute(
        self,
        side: str,
        binance: BinanceClientRpc,
        uniswap: UnichainV4Client,
        iteration_id: int,
        start_time,
    ):
        """
        Executes first CEX, then DEX for minimal slippage
        """
        try:
            binance_side, uniswap_side = self.side_mapping[side]
        except KeyError as e:
            raise ValueError(f"Invalid side value: {side}") from e

        # place CEX leg first
        t4 = time.perf_counter()
        response_binance = binance.execute_trade(binance_side)
        t5 = time.perf_counter()
        self.logger.info(
            "[#%d] %s Executed Binance %s: %s [L %.1f ms]",
            iteration_id,
            elapsed_ms(start_time),
            binance_side,
            response_binance["fills"],
            (t5 - t4) * 1000,
        )
        if response_binance["status"] != "FILLED":
            self.logger.warning("Unexpected Binance status: %s", response_binance)
            raise RuntimeError("Binance leg failed")

        # place DEX leg second
        t6 = time.perf_counter()
        receipt_uniswap = uniswap.execute_trade(uniswap_side)
        t7 = time.perf_counter()
        if receipt_uniswap.status != 1:
            self.logger.warning("Unexpected Uniswap receipt: %s", receipt_uniswap)
            raise RuntimeError("Uniswap leg failed")
        self.logger.info(
            "[#%d] %s Executed Uniswap %s: %s [L %.1f ms]",
            iteration_id,
            elapsed_ms(start_time),
            uniswap_side,
            "0x" + receipt_uniswap["transactionHash"].hex(),  # format
            (t7 - t6) * 1000,
        )
        return response_binance, receipt_uniswap
