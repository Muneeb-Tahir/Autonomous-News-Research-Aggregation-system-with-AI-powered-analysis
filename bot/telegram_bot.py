"""
Telegram bot for the News Intelligence Agent.

Handles all user commands via Telegram polling.
Routes queries to Top5Service for processing.
"""

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from services.top5_service import Top5Service
from utils.logger import get_logger

logger = get_logger(__name__)

# Telegram message length limit
MAX_MESSAGE_LENGTH = 4096


class NewsTelegramBot:
    """Telegram bot with news query command handlers.

    Commands:
        /start, /help — Show help message
        /top5 [category] — Top 5 news (optional category filter)
        /breaking — Current breaking news
        /latest — 5 most recently collected articles
        /status — System health check
    """

    def __init__(self, top5_service: Top5Service):
        """Initialize the Telegram bot.

        Args:
            top5_service: The core Top5Service for handling queries.
        """
        self.top5_service = top5_service
        self.app = None

        if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.strip().lower() in (
            "your-bot-token", "your-token", "your_bot_token",
        ) or ":" not in TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram bot token not configured or invalid. Bot will not start.")
            return

        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()
        logger.info("Telegram bot initialized")

    def _register_handlers(self):
        """Register all command and message handlers."""
        self.app.add_handler(CommandHandler("start", self._handle_help))
        self.app.add_handler(CommandHandler("help", self._handle_help))
        self.app.add_handler(CommandHandler("top5", self._handle_top5))
        self.app.add_handler(CommandHandler("breaking", self._handle_breaking))
        self.app.add_handler(CommandHandler("latest", self._handle_latest))
        self.app.add_handler(CommandHandler("status", self._handle_status))

        # Handle any text message as a natural language query
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text)
        )

        # Error handler
        self.app.add_error_handler(self._handle_error)

    # =============================================================
    # Command Handlers
    # =============================================================

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start and /help commands."""
        response = self.top5_service.handle_query("/help")
        await self._send_response(update, response)

    async def _handle_top5(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /top5 command with optional category argument.

        Examples:
            /top5       → All categories
            /top5 ai    → AI news only
            /top5 world → World news only
        """
        # Build the full query text including arguments
        args = " ".join(context.args) if context.args else ""
        query_text = f"/top5 {args}".strip()

        await update.message.reply_text("🔍 Analyzing news... Please wait.")

        response = self.top5_service.handle_query(query_text)
        await self._send_response(update, response)

    async def _handle_breaking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /breaking command."""
        response = self.top5_service.handle_query("/breaking")
        await self._send_response(update, response)

    async def _handle_latest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /latest command."""
        response = self.top5_service.handle_query("/latest")
        await self._send_response(update, response)

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        response = self.top5_service.handle_query("/status")
        await self._send_response(update, response)

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language text messages.

        Examples:
            'What's the biggest news today?'
            'Top 5 AI news from the last 6 hours'
        """
        text = update.message.text.strip()
        if not text:
            return

        await update.message.reply_text("🔍 Analyzing news... Please wait.")

        response = self.top5_service.handle_query(text)
        await self._send_response(update, response)

    # =============================================================
    # Utilities
    # =============================================================

    async def _send_response(self, update: Update, text: str):
        """Send a response, splitting if it exceeds Telegram's length limit.

        Args:
            update: Telegram update object.
            text: Response text to send.
        """
        if not text:
            text = "No response generated."

        # Split long messages
        chunks = self._split_message(text)

        for chunk in chunks:
            try:
                await update.message.reply_text(
                    chunk,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
            except Exception:
                # If Markdown parsing fails, send as plain text
                try:
                    await update.message.reply_text(
                        chunk,
                        disable_web_page_preview=True,
                    )
                except Exception as e:
                    logger.error(f"Failed to send Telegram message: {e}")

    async def send_breaking_alert(self, text: str):
        """Send a breaking news alert to the configured chat.

        Args:
            text: Formatted breaking news text.
        """
        if not self.app or not TELEGRAM_CHAT_ID:
            logger.warning("Cannot send breaking alert: bot or chat ID not configured")
            return

        try:
            await self.app.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            logger.info("Breaking news alert sent via Telegram")
        except Exception as e:
            logger.error(f"Failed to send breaking alert: {e}")

    def _split_message(self, text: str) -> list:
        """Split a long message into chunks that fit Telegram's limit.

        Tries to split at line boundaries for readability.

        Args:
            text: Full message text.

        Returns:
            List of text chunks, each <= MAX_MESSAGE_LENGTH.
        """
        if len(text) <= MAX_MESSAGE_LENGTH:
            return [text]

        chunks = []
        current = ""

        for line in text.split("\n"):
            if len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                if current:
                    chunks.append(current)
                current = line
            else:
                current += ("\n" + line) if current else line

        if current:
            chunks.append(current)

        return chunks

    async def _handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle bot errors."""
        logger.error(f"Telegram bot error: {context.error}")

    async def set_commands(self):
        """Set the bot's command menu in Telegram."""
        if not self.app:
            return

        commands = [
            BotCommand("top5", "Top 5 most important news"),
            BotCommand("breaking", "Current breaking news"),
            BotCommand("latest", "5 most recent articles"),
            BotCommand("status", "System health check"),
            BotCommand("help", "Show all commands"),
        ]

        try:
            await self.app.bot.set_my_commands(commands)
            logger.info("Telegram bot commands registered")
        except Exception as e:
            logger.error(f"Failed to set bot commands: {e}")

    def run_polling(self):
        """Start the bot in polling mode (blocking).

        This runs the bot's event loop. Call this as the last
        thing in main.py since it blocks.
        """
        if not self.app:
            logger.error("Cannot start bot: not initialized")
            return

        logger.info("Starting Telegram bot (polling mode)...")
        self.app.run_polling(drop_pending_updates=True)
