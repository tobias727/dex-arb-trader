import os
import logging
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
    """Entrypoint for trading bot"""
    logger = setup_logger("trading_bot")
    binance, uniswap, orchestrator, detector = init_clients(logger, testnet=TESTNET)

    while True:
        # 1. uniswap quote, 2. binance quote, 3. binance execution, 4. uniswap execution
        try:
            uniswap_bid_notional, uniswap_ask_notional = (
                uniswap.estimate_swap_price()
            )  # returns [price, gas]
            logger.info(
                "Uniswap: %s, %s",
                f"{uniswap_bid_notional[0]:_}",
                f"{uniswap_ask_notional[0]:_}",
            )
            binance_bid_notional, binance_ask_notional = binance.get_price()
            logger.info(
                "Binance: %s, %s", f"{binance_bid_notional:_}", f"{binance_ask_notional:_}"
            )
        # Graceful retry for quoting connection error
        except ConnectionError as e:
            logger.error("Iteration skipped due to data fetch error: %s", e)
            continue

        side, edge = detector.detect(
            binance_bid_notional,
            binance_ask_notional,
            uniswap_bid_notional[0],
            uniswap_ask_notional[0],
        )
        if side:
            logger.warning("Detected: %s, %s", side, f"{edge:_}")
            response_binance, receipt_unichain = orchestrator.execute(
                side, binance, uniswap
            )
            # log results and do aftermath
            logger.info(
                "Executed both legs successfully: \n%s\n\n%s",
                response_binance,
                receipt_unichain,
            )

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
