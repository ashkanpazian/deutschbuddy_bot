# utils/handler_guard.py
import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from .safe_telegram import safe_send

log = logging.getLogger("Guard")

def guard(user_friendly_msg_fa="⚠️ خطای موقت رخ داد؛ دوباره تلاش کن.",
          user_friendly_msg_de="⚠️ Ein vorübergehender Fehler ist aufgetreten. Bitte erneut versuchen."):
    def deco(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            try:
                return await func(update, context, *args, **kwargs)
            except Exception as e:
                log.exception(f"Handler error in {func.__name__}: {e}")
                try:
                    from utils.memory import get_user
                    lang = get_user(update.effective_chat.id).get("language", "fa")
                except Exception:
                    lang = "fa"
                msg = user_friendly_msg_fa if lang == "fa" else user_friendly_msg_de
                await safe_send(update, context, msg)
        return wrapper
    return deco
