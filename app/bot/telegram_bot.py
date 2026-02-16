"""Telegram bot implementation."""

import asyncio
from typing import Optional
from uuid import UUID

import structlog
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from app.config import get_settings
from app.security import get_secrets_manager
from app.approvals import get_approval_manager, ApprovalStatus

logger = structlog.get_logger(__name__)


class TelegramBot:
    """Telegram bot for AI assistant interaction."""

    def __init__(self):
        """Initialize Telegram bot."""
        self.settings = get_settings()
        self.secrets_manager = get_secrets_manager()
        self.approval_manager = get_approval_manager()
        self.application: Optional[Application] = None
        self.bot_token: Optional[str] = None

    async def initialize(self) -> None:
        """Initialize bot with token from Secrets Manager."""
        try:
            # Get bot token from AWS Secrets Manager
            self.bot_token = await self.secrets_manager.get_secret(
                self.settings.telegram_bot_token_secret
            )

            # Create application
            self.application = Application.builder().token(self.bot_token).build()

            # Add handlers
            self.application.add_handler(CommandHandler("start", self._handle_start))
            self.application.add_handler(CommandHandler("help", self._handle_help))
            self.application.add_handler(CommandHandler("status", self._handle_status))
            self.application.add_handler(CommandHandler("pending", self._handle_pending))
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
            )
            self.application.add_handler(CallbackQueryHandler(self._handle_callback))

            logger.info("Telegram bot initialized")

        except Exception as e:
            logger.error("Failed to initialize Telegram bot", error=str(e))
            raise

    async def start(self) -> None:
        """Start the bot."""
        if not self.application:
            raise RuntimeError("Bot not initialized")

        logger.info("Starting Telegram bot")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        # Start approval manager cleanup task
        self.approval_manager.start_cleanup_task()

    async def stop(self) -> None:
        """Stop the bot."""
        if self.application:
            logger.info("Stopping Telegram bot")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

        # Shutdown approval manager
        await self.approval_manager.shutdown()

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        welcome_message = (
            "🤖 *Welcome to your Personal AI Assistant!*\n\n"
            "I can help you with:\n"
            "• 🐙 GitHub operations (search, create issues, comment)\n"
            "• 🌤️ Weather information\n"
            "• 📅 Calendar management\n\n"
            "All state-changing actions require your approval for security.\n\n"
            "Use /help to see available commands."
        )
        await update.message.reply_text(welcome_message, parse_mode="Markdown")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        help_message = (
            "*Available Commands:*\n\n"
            "/start - Show welcome message\n"
            "/help - Show this help message\n"
            "/status - Check system status\n"
            "/pending - Show pending approval requests\n\n"
            "*How to use:*\n"
            "Just send me a message with what you want to do!\n\n"
            "Examples:\n"
            "• \"What's the weather in London?\"\n"
            "• \"List my GitHub repositories\"\n"
            "• \"Create a GitHub issue in myrepo/project\"\n"
            "• \"Show my calendar for today\"\n\n"
            "*Approvals:*\n"
            "When an action requires approval, I'll send you a message with Approve/Deny buttons."
        )
        await update.message.reply_text(help_message, parse_mode="Markdown")

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        status_message = (
            "✅ *System Status*\n\n"
            f"Environment: {self.settings.app_env}\n"
            f"Region: {self.settings.aws_region}\n"
            f"Model: {self.settings.anthropic_model}\n\n"
            "All systems operational!"
        )
        await update.message.reply_text(status_message, parse_mode="Markdown")

    async def _handle_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pending command."""
        chat_id = str(update.effective_chat.id)
        pending_requests = self.approval_manager.get_pending_requests(user_id=chat_id)

        if not pending_requests:
            await update.message.reply_text("No pending approval requests.")
            return

        message = "*Pending Approval Requests:*\n\n"
        for i, record in enumerate(pending_requests, 1):
            req = record.request
            message += (
                f"{i}. {req.action_description}\n"
                f"   ID: `{req.id}`\n"
                f"   Connector: {req.connector}\n"
                f"   Expires: {req.expires_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )

        await update.message.reply_text(message, parse_mode="Markdown")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages."""
        user_message = update.message.text
        chat_id = str(update.effective_chat.id)

        logger.info("Received message", chat_id=chat_id, message=user_message)

        # TODO: Integrate with AI (Claude) to process the message
        # For now, just acknowledge
        await update.message.reply_text(
            "🤖 Received your message! AI integration coming soon.\n\n"
            f"You said: _{user_message}_",
            parse_mode="Markdown",
        )

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle button callbacks for approvals."""
        query = update.callback_query
        await query.answer()

        # Parse callback data: "approve:<request_id>" or "deny:<request_id>"
        action, request_id_str = query.data.split(":", 1)
        request_id = UUID(request_id_str)

        try:
            if action == "approve":
                await self.approval_manager.respond_to_request(
                    request_id, ApprovalStatus.APPROVED
                )
                await query.edit_message_text("✅ *Approved!*\n\n" + query.message.text.split("\n\n", 1)[1], parse_mode="Markdown")
            elif action == "deny":
                await self.approval_manager.respond_to_request(
                    request_id, ApprovalStatus.DENIED
                )
                await query.edit_message_text("❌ *Denied!*\n\n" + query.message.text.split("\n\n", 1)[1], parse_mode="Markdown")
            else:
                await query.edit_message_text("Unknown action.")

        except ValueError as e:
            logger.error("Error handling approval callback", error=str(e))
            await query.edit_message_text(f"Error: {e}")

    async def send_approval_request(self, request_id: UUID, user_id: str, description: str, details: dict) -> None:
        """Send approval request to user via Telegram.

        Args:
            request_id: Approval request ID
            user_id: Telegram chat ID
            description: Action description
            details: Action details
        """
        if not self.application:
            raise RuntimeError("Bot not initialized")

        try:
            # Create inline keyboard with Approve/Deny buttons
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve:{request_id}"),
                    InlineKeyboardButton("❌ Deny", callback_data=f"deny:{request_id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Format message
            message = f"🔐 *Approval Required*\n\n{description}\n\n"
            if details:
                message += "*Details:*\n"
                for key, value in details.items():
                    message += f"• {key}: `{value}`\n"

            # Send message
            await self.application.bot.send_message(
                chat_id=int(user_id), text=message, reply_markup=reply_markup, parse_mode="Markdown"
            )

            logger.info("Sent approval request", request_id=str(request_id), user_id=user_id)

        except Exception as e:
            logger.error("Failed to send approval request", error=str(e))
            raise
