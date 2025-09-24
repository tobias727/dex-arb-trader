import os
import logging
import time
from src.engine.orchestrator import Orchestrator
from src.engine.detector import Detector
from src.binance.rpc_client import BinanceClientRpc
from src.unichain.clients.v4client import UnichainV4Client
from src.stream_data import load_pools
from src.config import (
    TOKEN0_INPUT,
)

TESTNET = True


def main():
    """
    Entrypoint for trading bot
    Execution pattern is:
        1. uniswap quote,
        2. binance quote,
        3. binance execution,
        4. uniswap execution
    time.perf_counter() is used for latency monitoring
    """
    logger = setup_logger("trading_bot")
    binance, uniswap, orchestrator, detector = init_clients(logger, testnet=TESTNET)
    iteration_id = 0

    while True:
        iteration_id += 1
        start_time = time.perf_counter()
        try:
            # 1. Uniswap quote
            t0 = time.perf_counter()
            uniswap_bid_notional, uniswap_ask_notional = (
                uniswap.estimate_swap_price()
            )  # returns [price, gas]
            t1 = time.perf_counter()
            logger.info(
                "[#%d] %s Uniswap: %s, %s [L %.1f ms]",
                iteration_id,
                elapsed_ms(start_time),
                f"{uniswap_bid_notional[0]:_}",
                f"{uniswap_ask_notional[0]:_}",
                (t1 - t0) * 1000,
            )
            # 2. Binance quote
            t2 = time.perf_counter()
            binance_bid_notional, binance_ask_notional = binance.get_price()
            t3 = time.perf_counter()
            logger.info(
                "[#%d] %s Binance: %s, %s [L %.1f ms]",
                iteration_id,
                elapsed_ms(start_time),
                f"{binance_bid_notional:_}",
                f"{binance_ask_notional:_}",
                (t3 - t2) * 1000,
            )
        # Graceful retry for quoting connection error
        except ConnectionError as e:
            logger.error("Iteration skipped due to data fetch error: %s", e)
            continue

        # 3. Detect
        side, edge = detector.detect(
            binance_bid_notional,
            binance_ask_notional,
            uniswap_bid_notional[0],
            uniswap_ask_notional[0],
        )

        # 4. Execute
        if side:
            logger.warning("Detected: %s, %s", side, f"{edge:_}")
            t4 = time.perf_counter()
            response_binance, receipt_unichain = orchestrator.execute(
                side, binance, uniswap
            )
            t5 = time.perf_counter()
            logger.info(
                "[#%d] %s Executed both legs successfully [L %.1f ms]\n%s\n\n%s",
                iteration_id,
                elapsed_ms(start_time),
                (t5 - t4) * 1000,
                response_binance,
                receipt_unichain,
            )


def elapsed_ms(start_time: float) -> str:
    """Return elapsed time since start in ms, formatted in brackets."""
    return f"[ET { (time.perf_counter() - start_time) * 1000:.1f} ms]"


def init_clients(logger, testnet: bool = False):
    """Initializes clients"""
    binance = BinanceClientRpc(logger, TOKEN0_INPUT, testnet)
    pools = load_pools("unichain_v4_pools.json")
    uniswap = UnichainV4Client(pools, logger, testnet)
    orchestrator = Orchestrator(logger)
    detector = Detector(logger)
    return binance, uniswap, orchestrator, detector


def setup_logger(name: str, log_dir: str = "out/logs") -> logging.Logger:
    """Create and configure logger with console + file handlers."""
    log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{name}.log")

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    # File handler
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setFormatter(log_formatter)

    # Logger setup
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


if __name__ == "__main__":
    main()
