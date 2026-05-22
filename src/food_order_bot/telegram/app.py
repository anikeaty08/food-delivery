from telegram.ext import Application, CommandHandler, MessageHandler, filters

from food_order_bot.telegram import handlers
from food_order_bot.settings import Settings


def build_telegram_app(settings: Settings) -> Application | None:
    if not settings.telegram_bot_token:
        return None
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("connect", handlers.connect))
    app.add_handler(CommandHandler("search", handlers.search))
    app.add_handler(CommandHandler("menu", handlers.menu))
    app.add_handler(CommandHandler("cart", handlers.cart))
    app.add_handler(CommandHandler("checkout", handlers.checkout))
    app.add_handler(CommandHandler("track", handlers.track))
    app.add_handler(CommandHandler("dineout", handlers.search))
    app.add_handler(CommandHandler("cancel", handlers.cancel))
    app.add_handler(CommandHandler("confirm", handlers.confirm))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.text_message))
    return app
