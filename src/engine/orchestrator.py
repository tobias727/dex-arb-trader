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
            return response_binance

        def _execute_dex_leg():
            t6 = time.perf_counter()
            receipt_uniswap = uniswap.execute_trade(u_side)
            t7 = time.perf_counter()
            self.logger.info(
                "[#%d] %s Executed Uniswap %s: %s [L %.1f ms]",
                iteration_id,
                elapsed_ms(start_time),
                u_side,
                "0x" + receipt_uniswap["transactionHash"].hex(),  # format
                (t7 - t6) * 1000,
            )
            return receipt_uniswap

        def _rollback_successful_trade(side: str, client):
            """Rolls back a successful trade if the other leg fails."""
            self.logger.info("Rolling back successful trade...")
            # TODO: implement

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_binance = executor.submit(_execute_cex_leg)
            future_uniswap = executor.submit(_execute_dex_leg)

            try:
                response_binance = future_binance.result()
            except Exception as e:
                self.logger.error("Error executing Binance leg: %s", e)

            try:
                receipt_uniswap = future_uniswap.result()
            except Exception as e:
                self.logger.error("Error executing Uniswap leg: %s", e)

        # handle partial execution
        if (
            response_binance
            and response_binance["status"] == "FILLED"
            and (not receipt_uniswap or receipt_uniswap.status != 1)
        ):
            self.logger.warning("Uniswap leg failed. Rolling back Binance leg.")
            _rollback_successful_trade(b_side, binance)

        elif (
            receipt_uniswap
            and receipt_uniswap.status == 1
            and (not response_binance or response_binance["status"] != "FILLED")
        ):
            self.logger.warning("Binance leg failed. Rolling back Uniswap leg.")
            _rollback_successful_trade(u_side, uniswap)
