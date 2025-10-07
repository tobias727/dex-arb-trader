import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler
from src.config import (
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
)


class TelegramBot:
    """Messaging trading bot via Telegram"""

    def __init__(self):
        self.kill_switch = False
        self.application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        self.application.add_handler(CommandHandler("kill", self._handle_kill))
        asyncio.get_event_loop().run_in_executor(None, self.application.run_polling)

    async def notify_executed(self):
        """Sends a message when a trade is executed"""
        message = "💰 Trade executed successfully!"
        await self.application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
