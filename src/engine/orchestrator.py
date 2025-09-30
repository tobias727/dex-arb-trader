import time
from concurrent.futures import ThreadPoolExecutor
from src.binance.rpc_client import BinanceClientRpc
from src.unichain.clients.v4client import UnichainV4Client
from src.utils.utils import elapsed_ms


class Orchestrator:
    """Responsible for executing two-leg trade"""

    def __init__(self, logger):
        self.logger = logger

    def execute(
        self,
        b_side: str,
        u_side: str,
        binance: BinanceClientRpc,
        uniswap: UnichainV4Client,
        iteration_id: int,
        start_time,
    ):
        """
        Executes first CEX, then DEX for minimal slippage
        """
        def _execute_cex_leg():
            t4 = time.perf_counter()
            response_binance = binance.execute_trade(b_side)
            t5 = time.perf_counter()
            self.logger.info(
                "[#%d] %s Executed Binance %s: %s [L %.1f ms]",
                iteration_id,
                elapsed_ms(start_time),
                b_side,
                response_binance["fills"],
                (t5 - t4) * 1000,
            )
            if response_binance["status"] != "FILLED":
                self.logger.warning("Unexpected Binance status: %s", response_binance)
                raise RuntimeError("Binance leg failed")
            return response_binance

        def _execute_dex_leg():
            t6 = time.perf_counter()
            receipt_uniswap = uniswap.execute_trade(u_side)
            t7 = time.perf_counter()
            if receipt_uniswap.status != 1:
                self.logger.warning("Unexpected Uniswap receipt: %s", receipt_uniswap)
                raise RuntimeError("Uniswap leg failed")
            self.logger.info(
                "[#%d] %s Executed Uniswap %s: %s [L %.1f ms]",
                iteration_id,
                elapsed_ms(start_time),
                u_side,
                "0x" + receipt_uniswap["transactionHash"].hex(),  # format
                (t7 - t6) * 1000,
            )
            return receipt_uniswap

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_binance = executor.submit(_execute_cex_leg)
            future_uniswap = executor.submit(_execute_dex_leg)

            response_binance = future_binance.result()
            receipt_uniswap = future_uniswap.result()

        return response_binance, receipt_uniswap
