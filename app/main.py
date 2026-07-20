from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.config.settings import settings
from app.bot.handlers import start_command, handle_audio
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def main() -> None:
    if not settings.bot_token:
        logger.error("BOT_TOKEN is not set. Create a .env file based on .env.example")
        return

    app = (
        Application.builder()
        .token(settings.bot_token)
        .read_timeout(120)
        .write_timeout(120)
        .connect_timeout(60)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.ALL, handle_audio))

    logger.info("Bot started. Max usage: %d", settings.max_usage_per_user)
    app.run_polling()


if __name__ == "__main__":
    main()
