import logging
from typing import Optional, Iterable
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes

log = logging.getLogger("SafeTG")
TG_LIMIT = 4096

def _chunks(s: str, n: int) -> Iterable[str]:
    for i in range(0, len(s), n):
        yield s[i:i+n]

async def safe_send(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    parse_mode: Optional[str] = "Markdown",
    reply_markup: Optional[InlineKeyboardMarkup] = None
):

    try:
        chat_id = update.effective_chat.id
        for part in _chunks(text, TG_LIMIT):
            if update.callback_query:
                await context.bot.send_message(chat_id=chat_id, text=part, parse_mode=parse_mode, reply_markup=reply_markup)
                reply_markup = None  # فقط پیام اول دکمه داشته باشد
            else:
                await update.message.reply_text(part, parse_mode=parse_mode, reply_markup=reply_markup)
                reply_markup = None
    except Exception as e:
        log.exception(f"Telegram send error: {e}")
