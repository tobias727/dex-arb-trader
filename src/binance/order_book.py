from binance.client import Client
from src.config import BINANCE_API_KEY, BINANCE_API_SECRET

class BinanceClient:
    """Wrapper for Binance API Client"""
    def __init__(self):
        self.client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

    def get_order_book(self, symbol, limit=100):
        """ Returns the order book given a symbol (eg. 'ETHUSDC')"""
        try:
            order_book = self.client.get_order_book(symbol=symbol, limit=limit)
            bids = order_book['bids']
            asks = order_book['asks']
            return (bids, asks)
        except Exception as e:
            print(f"Error during get_order_book: {e}")
            return None
