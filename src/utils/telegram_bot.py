from telegram.ext import ApplicationBuilder
from config import (
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
)


class TelegramBot:
    """Messaging trading bot via Telegram"""

    def __init__(self):
        self.application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def notify_executed(self, pnl):
        """Sends a message when a trade is executed"""
        message = f"💰 Trade executed successfully! PnL: ${pnl}"
        await self.application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

    async def notify_crashed(self, e):
        """Sends a message when an Exception occurs"""
        message = f"❌ Trading bot crashed!\n\nException: {e}"
        await self.application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        self.application.stop_running()
