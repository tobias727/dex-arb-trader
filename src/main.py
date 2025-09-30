import os
import logging
from concurrent.futures import ThreadPoolExecutor
import time
from src.engine.orchestrator import Orchestrator
from src.engine.detector import Detector
from src.binance.rpc_client import BinanceClientRpc
from src.unichain.clients.v4client import UnichainV4Client
from src.stream_data import load_pools
from src.utils.utils import elapsed_ms, check_pre_trade
from src.utils.types import NotionalValues
from src.config import (
    TOKEN0_INPUT,
)

TESTNET = True


def main():
    """
    Entrypoint for trading bot
    Execution pattern is:
        1. binance + uniswap quote,
        2. binance + uniswap execution,
    time.perf_counter() is used for latency monitoring
    """
    out_log_name = "trading_bot" if TESTNET else "trading_bot_LIVE"
    logger = setup_logger(out_log_name)
    binance, uniswap, orchestrator, detector = init_clients(logger, testnet=TESTNET)
    balances = log_balances(binance, uniswap, logger, TESTNET)
    iteration_id = 0  # TODO: get from file and append
    # TODO: check if permit2 approval is set (> ? )

    # in live mode, only execute once to test
    has_executed = False

    while True:
        iteration_id += 1
        start_time = time.perf_counter()

        # 1. Get Binance/Uniswap quotes
        quotes = get_quotes(logger, iteration_id, start_time, uniswap, binance)
        if quotes is None:
            continue  # skip if iteration is failed

        # 2. Detect
        b_side, u_side, edge = detector.detect(quotes)

        # 3. Execute
        if edge and not has_executed:
            logger.warning("Detected: %s, CEX_%s_DEX, %s", b_side, u_side, f"{edge:_}")
            # quit if balances too low
            check_pre_trade(
                logger,
                balances,
                b_side,
                u_side,
                quotes,
                buffer=1.01,
            )

            orchestrator.execute(
                b_side, u_side, binance, uniswap, iteration_id, start_time
            )

            if not TESTNET:  # only do one trade for now for LIVE
                has_executed = True

            logger.info(
                "[#%d] %s Finished iteration...",
                iteration_id,
                elapsed_ms(start_time),
            )
            balances = log_balances(binance, uniswap, logger, TESTNET)


def get_quotes(
    logger: logging.Logger,
    iteration_id,
    start_time,
    uniswap: UnichainV4Client,
    binance: BinanceClientRpc,
) -> NotionalValues:
    """Fetch quotes from Uniswap and Binance"""

    def _fetch_uniswap():
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
        return uniswap_bid_notional, uniswap_ask_notional

    def _fetch_binance():
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
        return binance_bid_notional, binance_ask_notional

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_uniswap = executor.submit(_fetch_uniswap)
            future_binance = executor.submit(_fetch_binance)

            u_bid, u_ask = future_uniswap.result()
            b_bid, b_ask = future_binance.result()

        return NotionalValues(
            b_bid,
            b_ask,
            u_bid[0],
            u_ask[0],
        )
    except Exception as e:
        logger.error("Iteration skipped due to data fetch error: %s", e)
        return None


def log_balances(
    binance: BinanceClientRpc,
    uniswap: UnichainV4Client,
    logger: logging.Logger,
    testnet: bool = False,
):
    """Logs Balances for Binance and Unichain"""
    testnet_flag = "[TESTNET] " if testnet else ""
    b_eth, b_usdc = binance.get_account_info()
    logger.info(
        testnet_flag + "BALANCES BINANCE: ETH %s, USDC %s",
        b_eth,
        b_usdc,
    )
    u_eth, u_usdc = uniswap.get_balances()
    logger.info(
        testnet_flag + "BALANCES UNISWAP: ETH %s, USDC %s",
        u_eth,
        u_usdc,
    )
    return {
        "binance": {"ETH": b_eth, "USDC": b_usdc},
        "uniswap": {"ETH": u_eth, "USDC": u_usdc},
    }


def init_clients(logger: logging.Logger, testnet: bool = False):
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
