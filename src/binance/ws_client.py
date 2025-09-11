import os
from datetime import datetime
import asyncio
import json
import csv
import websockets
from src.config import (
    UPDATE_INTERVAL,
    ORDER_BOOK_DEPTH,
    BINANCE_TOKEN_PAIRS,
    BINANCE_BASE_URL_WS,
)


class BinanceClient:
    """Stream data from Binance"""

    def __init__(self, logger):
        update_interval = UPDATE_INTERVAL
        order_book_depth = ORDER_BOOK_DEPTH
        token_pairs = BINANCE_TOKEN_PAIRS
        streams = "/".join(
            [
                f"{pair}@depth{order_book_depth}@{update_interval}"
                for pair in token_pairs
            ]
        )
        self.binance_ws_url = f"{BINANCE_BASE_URL_WS}/stream?streams={streams}"
        self.logger = logger
        self.order_book = []
        # Producer-consumer messaging queue
        self.message_queue = asyncio.Queue()

    async def ws_stream(self):
        """Method to stream order book via WebSocket"""
        async with websockets.connect(self.binance_ws_url) as websocket:
            self.logger.info(f"🌐 Connected ws: {self.binance_ws_url}")
            while True:
                try:
                    receive_time = (
                        datetime.now()
                        .replace(microsecond=0)
                        .strftime("%Y-%m-%d %H:%M:%S.%f")
                    )
                    # fetch message
                    raw_message = await websocket.recv()

                    # add to queue
                    message_package = {
                        "raw_message": raw_message,
                        "receive_time": receive_time,
                    }
                    await self.message_queue.put(message_package)
                except websockets.ConnectionClosed as e:
                    self.logger.info(f"❌ WebSocket connection closed: {e}")
                    break
                except Exception as e:
                    self.logger.error(f"❌ Error in WebSocket stream: {e}")
                    break

    async def process_messages(self):
        """Method to process message queue"""
        while True:
            try:
                # load message + timestamp
                message_package = await self.message_queue.get()
                raw_message, receive_time = (
                    message_package["raw_message"],
                    message_package["receive_time"],
                )

                # Parse JSON message
                message = json.loads(raw_message)

                # Extract token pair and stream information
                stream_name = message.get("stream")
                token_pair = stream_name.split("@")[0]
                raw_payload = message.get("data")

                if raw_payload:
                    raw_payload["time"] = receive_time
                    raw_payload["token_pair"] = token_pair
                    self.order_book.append(raw_payload)
                    self.logger.info(
                        f"📥 Processed new order book for '{token_pair}' at {receive_time}"
                    )

                # finished
                self.message_queue.task_done()
            except Exception as e:
                self.logger.error(f"❌ Error processing message: {e}")

    async def run(self, duration=5):
        """Main method to stream and process data"""
        websocket_task = asyncio.create_task(self.ws_stream())
        process_task = asyncio.create_task(self.process_messages())

        # runs for duration
        await asyncio.sleep(duration)

        # stops tasks
        websocket_task.cancel()
        process_task.cancel()

        await asyncio.gather(websocket_task, process_task, return_exceptions=True)
        self.logger.info("✅ Terminated tasks")

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
