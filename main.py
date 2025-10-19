import os
import time
import random
import logging

from dotenv import load_dotenv
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, Application
)
from telegram.error import NetworkError, RetryAfter, TimedOut

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("DeutschBuddy")

# ---------- ENV ----------
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL       = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Set TELEGRAM_BOT_TOKEN and OPENAI_API_KEY in .env")

def _mask(s: str) -> str:
    if not s: return "None"
    return (s[:6] + "..." + s[-4:]) if len(s) > 12 else "***"

# ---------- Internal modules (بعد از load_dotenv) ----------
from modules.onboarding import greet, handle_language_choice
from modules.level_test import start_level_test as level_start, handle_answer
from modules.schreiben import schreiben_correct
from modules.wortschatz import vocab_daily
from modules.dictionary import lookup
from modules.grammar import grammar_tip
from modules.menu import open_menu, set_goal, show_profile, handle_menu_action, handle_goal_set
from modules.daily import daily, daily_check_answer

# ---------- Error handler ----------
def on_error(update, context):
    log.exception("Unhandled exception", exc_info=context.error)
    try:
        chat = getattr(update, "effective_chat", None)
        if chat and chat.id:
            context.bot.send_message(chat_id=chat.id, text="⚠️ یک خطای موقت رخ داد؛ دوباره تلاش می‌کنم.")
    except Exception:
        pass

# ---------- Build application ----------
def build_app() -> Application:
    request = HTTPXRequest(
        http_version="1.1",
        connect_timeout=30.0,
        read_timeout=120.0,
        write_timeout=30.0,
        pool_timeout=60.0,
    )

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(request)
        .concurrent_updates(True)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", greet))
    app.add_handler(CommandHandler("menu", open_menu))
    app.add_handler(CommandHandler("level", level_start))
    app.add_handler(CommandHandler("wortschatz", vocab_daily))
    app.add_handler(CommandHandler("dict", lookup))
    app.add_handler(CommandHandler("grammar", grammar_tip))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("schreiben", lambda u, c: u.message.reply_text("متن آلمانی‌ات را بفرست تا تصحیح کنم.")))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, daily_check_answer))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, schreiben_correct))

    app.add_handler(CallbackQueryHandler(handle_language_choice, pattern=r"^lang:(de|fa)$"))
    app.add_handler(CallbackQueryHandler(set_goal, pattern=r"^goal:(lernen|review)$"))
    app.add_handler(CallbackQueryHandler(handle_goal_set, pattern=r"^goal:set:(lernen|review)$"))
    app.add_handler(CallbackQueryHandler(handle_answer, pattern=r"^ans:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(level_start, pattern=r"^level:start$"))
    app.add_handler(CallbackQueryHandler(open_menu,   pattern=r"^level:skip$"))
    app.add_handler(CallbackQueryHandler(open_menu,   pattern=r"^level:continue$"))
    app.add_handler(CallbackQueryHandler(level_start, pattern=r"^level:redo$"))
    app.add_handler(CallbackQueryHandler(show_profile, pattern=r"^menu:profile$"))
    app.add_handler(CallbackQueryHandler(handle_menu_action, pattern=r"^menu:(daily|schreiben|wortschatz|dict|grammar|back)$"))

    app.add_error_handler(on_error)
    return app

def run_with_reconnect():
    attempt = 0
    while True:
        app = build_app()
        try:
            log.info("===== DeutschBuddy starting (Polling) =====")
            log.info(f"TELEGRAM_BOT_TOKEN: {_mask(TELEGRAM_BOT_TOKEN)}")
            log.info(f"OPENAI_API_KEY   : {_mask(OPENAI_API_KEY)}")
            log.info(f"OPENAI_MODEL     : {OPENAI_MODEL}")

            log.info("Bot is now polling… (Ctrl+C to stop)")

            app.run_polling(close_loop=False)
            attempt = 0
            log.info("Polling stopped gracefully.")
            break

        except RetryAfter as e:
            wait = max(5, int(getattr(e, "retry_after", 10)))
            log.warning(f"RetryAfter from Telegram. Waiting {wait}s…")
            time.sleep(wait)
            attempt += 1

        except (NetworkError, TimedOut) as e:
            attempt += 1
            base = min(300, 2 ** min(attempt, 8))  # سقف ۵ دقیقه
            jitter = random.uniform(0.2, 0.5) * base
            wait = int(base + jitter)
            log.warning(f"Network error: {e}. Reconnecting in {wait}s (attempt {attempt})…")
            time.sleep(wait)

        except Exception as e:
            attempt += 1
            base = min(120, 2 ** min(attempt, 6))  # سقف ۲ دقیقه
            jitter = random.uniform(0.2, 0.5) * base
            wait = int(base + jitter)
            logging.exception(f"Unexpected error: {e}. Restarting in {wait}s…")
            time.sleep(wait)


def main():
    try:
        run_with_reconnect()
    except KeyboardInterrupt:
        log.info("Shutting down by user (Ctrl+C). Bye!")

if __name__ == "__main__":
    main()
