import os
import logging
import time
from src.engine.orchestrator import Orchestrator
from src.engine.detector import Detector
from src.binance.rpc_client import BinanceClientRpc
from src.unichain.clients.v4client import UnichainV4Client
from src.stream_data import load_pools
from src.utils.utils import elapsed_ms
from src.config import (
    TOKEN0_INPUT,
)

TESTNET = False


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
    out_log_name = "trading_bot" if TESTNET else "trading_bot_LIVE"
    logger = setup_logger(out_log_name)
    binance, uniswap, orchestrator, detector = init_clients(logger, testnet=TESTNET)
    log_balances(binance, uniswap, logger, TESTNET)
    iteration_id = 0

    # in live mode, only execute once to test
    has_executed = False

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
        except Exception as e:
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
        if side and not has_executed:
            logger.warning("Detected: %s, %s", side, f"{edge:_}")
            response_binance, receipt_unichain = orchestrator.execute(
                side, binance, uniswap, iteration_id, start_time
            )
            if not TESTNET:  # only do one trade for now for LIVE
                has_executed = True
            logger.info(
                "[#%d] %s Finished iteration...",
                iteration_id,
                elapsed_ms(start_time),
            )
            log_balances(binance, uniswap, logger, TESTNET)


def log_balances(
    binance: BinanceClientRpc, uniswap: UnichainV4Client, logger, testnet: bool = False
):
    """Logs Balances for Binance and Unichain"""
    testnet_flag = "[TESTNET] " if testnet else ""
    try:
        balance_eth, balance_usdc = binance.get_account_info()
        logger.info(
            testnet_flag + "BALANCES BINANCE: ETH %s, USDC %s",
            balance_eth,
            balance_usdc,
        )
    except Exception as e:
        logger.error(testnet_flag + "Failed to load Binance balances: %s", e)
    try:
        balance_eth, balance_usdc = uniswap.get_balances()
        logger.info(
            testnet_flag + "BALANCES UNISWAP: ETH %s, USDC %s",
            balance_eth,
            balance_usdc,
        )
    except Exception as e:
        logger.error(testnet_flag + "Failed to load Unichain balances: %s", e)


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
