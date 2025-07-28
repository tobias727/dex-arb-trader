import os
import csv
import json
import asyncio
import websockets
from src.config import OUTPUT_DIRECTORY

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/ethusdc@depth10@1000ms"  # 10 level, 1 sec
order_book_data = []  # List to store order book updates

async def connect_to_binance():
    """Collects order book updates from Binance WebSocket and stores them in a list."""
    async with websockets.connect(BINANCE_WS_URL) as websocket:
        print(f"Successfully connected to: {BINANCE_WS_URL}")
        try:
            while True:
                data = await websocket.recv()
                order_book = json.loads(data)
                print(f"Order book update:\n{order_book}")
                order_book_data.append(order_book)
        except websockets.ConnectionClosed as e:
            print(f"WebSocket closed: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

def save_to_csv():
    """Saves the collected order book data to a CSV file."""
    if not order_book_data:
        print("No data to save.")
        return
    output_dir = os.path.join(OUTPUT_DIRECTORY, "data")
    print(output_dir)
    csv_file_name = os.path.join(output_dir, "order_book.csv")

    with open(csv_file_name, mode="w", newline="", encoding="utf-8") as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["time", "bids", "asks"])
        for data in order_book_data:
            timestamp = data.get("lastUpdateId")
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            csv_writer.writerow([timestamp, bids, asks])

    print(f"Data successfully saved to {csv_file_name}.")

def main():
    """Starts the WebSocket connection and handles KeyboardInterrupt."""
    try:
        asyncio.run(connect_to_binance())
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt: saving data to CSV...")
        save_to_csv()

if __name__ == "__main__":
    main()
