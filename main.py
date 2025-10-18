import os
from dotenv import load_dotenv
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from openai import OpenAI
from modules.onboarding import greet, handle_language_choice
from modules.level_test import start_level_test, handle_answer
from modules.menu import open_menu, set_goal
from modules.schreiben import schreiben_correct
from modules.wortschatz import vocab_daily
from modules.dictionary import lookup
from modules.grammar import grammar_tip
from modules.menu import open_menu, set_goal, show_profile, handle_menu_action, handle_goal_set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("DeutschBuddy")

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Set TELEGRAM_BOT_TOKEN and OPENAI_API_KEY in .env")

client = OpenAI(api_key=OPENAI_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await greet(update, context)

async def level_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # allow starting test anytime
    from modules.level_test import start_level_test as run
    await run(update, context)

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await open_menu(update, context)

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).concurrent_updates(True).build()
    # commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("level", level_cmd))
    app.add_handler(CommandHandler("wortschatz", vocab_daily))
    app.add_handler(CommandHandler("dict", lookup))
    app.add_handler(CommandHandler("grammar", grammar_tip))
    # schreiben: any non-command text when user intends—keep simple demo with /schreiben context
    app.add_handler(CommandHandler("schreiben", lambda u,c: u.message.reply_text("متن آلمانی‌ات را بفرست تا تصحیح کنم.")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, schreiben_correct))
    # callbacks
    app.add_handler(CallbackQueryHandler(handle_language_choice, pattern=r"^lang:(de|fa)$"))
    app.add_handler(CallbackQueryHandler(set_goal, pattern=r"^goal:(lernen|review)$"))
    app.add_handler(CallbackQueryHandler(handle_answer, pattern=r"^ans:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(level_cmd, pattern=r"^level:start$"))
    app.add_handler(CallbackQueryHandler(menu_cmd, pattern=r"^level:skip$"))
    app.add_handler(CallbackQueryHandler(show_profile, pattern=r"^menu:profile$"))
    app.add_handler(CallbackQueryHandler(handle_menu_action, pattern=r"^menu:(schreiben|wortschatz|dict|grammar|back)$"))
    app.add_handler(CallbackQueryHandler(level_cmd, pattern=r"^level:start$"))
    app.add_handler(CallbackQueryHandler(menu_cmd, pattern=r"^level:skip$"))
    app.add_handler(CallbackQueryHandler(menu_cmd, pattern=r"^level:continue$"))
    app.add_handler(CallbackQueryHandler(level_cmd, pattern=r"^level:redo$"))
    app.add_handler(CallbackQueryHandler(handle_goal_set, pattern=r"^goal:set:(lernen|review)$"))

    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
