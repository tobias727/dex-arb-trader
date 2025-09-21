import logging
from src.engine.orchestrator import Orchestrator
from src.engine.detector import Detector
from src.binance.rpc_client import BinanceClientRpc
from src.unichain.clients.v4client import UnichainV4Client
from src.stream_data import load_pools
from src.config import (
    TOKEN0_INPUT,
)


def main():
    """Entrypoint for trading bot"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)
    orchestrator = Orchestrator()
    detector = Detector(logger)
    binance = BinanceClientRpc(logger, TOKEN0_INPUT)

    # Load pools from JSON
    pools_filepath = "unichain_v4_pools.json"
    pools = load_pools(pools_filepath)
    uniswap = UnichainV4Client(pools, logger)

    while True:
        # 1. uniswap quote, 2. binance quote, 3. binance execution, 4. uniswap execution
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
        side, edge = detector.detect(
            binance_bid_notional,
            binance_ask_notional,
            uniswap_bid_notional[0],
            uniswap_ask_notional[0],
        )
        if side:
            print("Detected: ", side, edge)


if __name__ == "__main__":
    main()
