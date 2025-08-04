import os
from datetime import datetime
import time
import json
import csv
import websockets
from src.config import (
    UPDATE_INTERVAL,
    ORDER_BOOK_DEPTH,
    BINANCE_TOKEN_PAIR,
    BINANCE_BASE_URL_WS,
)


class BinanceClient:
    """Stream data from Binance"""

    def __init__(self, logger):
        token_pair = BINANCE_TOKEN_PAIR
        update_interval = UPDATE_INTERVAL
        order_book_depth = ORDER_BOOK_DEPTH
        self.binance_ws_url = f"{BINANCE_BASE_URL_WS}/{token_pair}@depth{order_book_depth}@{update_interval}"
        self.logger = logger
        self.order_book = []

    async def ws_stream(self, duration=5):
        """Method to stream order book via WebSocket"""
        is_streaming = True
        start_time = time.time()
        async with websockets.connect(self.binance_ws_url) as websocket:
            self.logger.info(f"🌐 Connected ws: {self.binance_ws_url}")
            while is_streaming:
                try:
                    if duration and time.time() - start_time >= duration:
                        is_streaming = False
                        self.logger.info("✅ Terminated WebSocket connection")
                        break
                    # fetch data
                    data = await websocket.recv()
                    order_book = json.loads(data)
                    now_rounded_sec = (
                        datetime.now()
                        .replace(microsecond=0)
                        .strftime("%Y-%m-%d %H:%M:%S.%f")
                    )
                    order_book["time"] = now_rounded_sec
                    self.order_book.append(order_book)
                    self.logger.info(f"New Order Book fetched at {now_rounded_sec}")
                except websockets.ConnectionClosed as e:
                    self.logger.info(f"❌ WebSocket connection closed: {e}")
                    break

    def save_to_csv(self, output_path, latest=False):
        """Save WebSocket data to csv"""
        if not self.order_book:
            self.logger.info("No data to save.")
            return

        # unique output file name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if latest:
            output_file = os.path.join(output_path, "latest_binance_ws_orderbook.csv")
        else:
            output_file = os.path.join(
                output_path, f"{timestamp}_binance_ws_orderbook.csv"
            )

        try:
            headers = self.order_book[0].keys()
            with open(output_file, mode="w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(self.order_book)
                self.logger.info(f"📁 Saved Binance order book data to {output_file}")
        except Exception as e:
            self.logger.error(f"❌ Error saving to CSV: {e}")
