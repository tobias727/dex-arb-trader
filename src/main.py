import logging
from src.engine.orchestrator import Orchestrator
from src.engine.detector import Detector
from src.binance.rpc_client import BinanceClientRpc
from src.unichain.clients.v4client import UnichainV4Client
from src.stream_data import load_pools

def main():
    """Entrypoint for """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)
    orchestrator = Orchestrator()
    detector = Detector(logger)
    binance = BinanceClientRpc(logger)

    # Load pools from JSON
    pools_filepath = "unichain_v4_pools.json"
    pools = load_pools(pools_filepath)
    uniswap = UnichainV4Client(pools, logger)


    while True:
        binance_best_bid, binance_best_ask = binance.get_price()
        print("Binance: ",binance_best_bid, binance_best_ask)
        uniswap_best_bid, uniswap_best_ask = uniswap.estimate_swap_price() # returns [price, gas]
        print("Uniswap: ",uniswap_best_bid[0], uniswap_best_ask[0])

        side, edge = detector.detect(binance_best_bid, binance_best_ask, uniswap_best_bid[0], uniswap_best_ask[0])
        if side:
            print("Detected: ",side, edge)

if __name__ == "__main__":
    main()
