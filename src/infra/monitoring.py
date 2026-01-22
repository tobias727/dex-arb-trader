import os
import csv
import asyncio
import aiohttp
from telegram.ext import ApplicationBuilder
from config import (
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
)


class TelegramBot:
    """Messaging trading bot via Telegram"""

    def __init__(self):
        self.application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def _send(self, text: str) -> None:
        await self.application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)

    async def notify_executed(self, pnl):
        """Sends a message when a trade is executed"""
        message = f"💰 Trade executed successfully! PnL: ${pnl}"
        await self._send(message)

    async def notify_crashed(self, e):
        """Sends a message when an Exception occurs"""
        message = f"❌ Trading bot crashed!\n\nException: {e}"
        await self._send(message)
        self.application.stop_running()


async def fetch_public_ip():
    """Returns IP-Address to monitor for binance allowlist"""
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.ipify.org?format=json") as r:
            data = await r.json()
            return data["ip"]


async def monitor_ip_change(logger, interval=300):
    """Check if the IP address changed (last 5 minutes)"""
    initial_ip = await fetch_public_ip()
    logger.info(f"Initial IP: {initial_ip}")
    while True:
        await asyncio.sleep(interval)
        current_ip = await fetch_public_ip()
        if current_ip != initial_ip:
            raise RuntimeError(
                f"Public IP changed: {initial_ip} -> {current_ip}. Aborting for security."
            )


def append_row_to_csv(filename: str, row: dict) -> None:
    """Appends trades to csv file in out/, adds current CET timestamp"""
    out_path = os.path.join("out", filename)
    os.makedirs("out", exist_ok=True)
    file_exists = os.path.isfile(out_path)
    with open(out_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
