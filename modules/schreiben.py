# modules/schreiben.py
import os
import time
import random
import logging
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.session import touch_user
from utils.memory import get_user
from utils.safe_telegram import safe_send
from utils.handler_guard import guard

load_dotenv()
log = logging.getLogger("Schreiben")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_TEXT = (
    "You are a precise German teacher (B1/B2). "
    "Always reply in a clear 4-part Markdown format:\n"
    "1) **Titel (DE)**\n"
    "2) **Verbesserter Text (DE)**\n"
    "3) **Hinweise (DE)** — up to 3 bullets\n"
    "4) **ترجمهٔ فارسی**\n"
    "Keep it concise and exam-oriented."
)

SYSTEM_IMAGE = (
    "You are a precise German teacher (B1/B2) with OCR ability. "
    "Input may contain an image. Extract readable German text (OCR) and correct it. "
    "Return Markdown with: Titel, short OCR-Text, Verbesserter Text, up to 3 Hinweise (DE), ترجمهٔ فارسی."
)

MAX_INPUT_CHARS = 1200
TG_LIMIT = 4096

def _truncate(s: str, limit: int = MAX_INPUT_CHARS) -> str:
    s = (s or "").strip()
    return s if len(s) <= limit else s[:limit] + " …"

def _retry_chat(messages, temperature=0.3, max_attempts=3):
    attempt = 0
    while True:
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=temperature
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            attempt += 1
            if attempt >= max_attempts:
                log.exception("OpenAI failed after %s attempts", attempt)
                raise
            base = min(10, 2 ** attempt)
            jitter = random.uniform(0.2, 0.5) * base
            time.sleep(base + jitter)

def _next_actions_kb(lang: str) -> InlineKeyboardMarkup:
    again = "✍️ ارسال متن بعدی" if lang == "fa" else "✍️ Nächsten Text senden"
    back  = "⬅️ بازگشت به منو" if lang == "fa" else "⬅️ Zurück zum Menü"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(again, callback_data="schreiben:again")],
        [InlineKeyboardButton(back,  callback_data="menu:back")]
    ])

async def _answer_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: str = "Markdown"):
    text = text or ""
    # تلگرام پیام‌های بلند را می‌بُرد؛ تکه‌تکه می‌فرستیم
    for i in range(0, len(text), TG_LIMIT):
        await safe_send(update, context, text[i:i+TG_LIMIT], parse_mode=parse_mode)

@guard()
async def schreiben_correct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_chat.id, "schreiben")

    chat_id = update.effective_chat.id
    user_lang = get_user(chat_id).get("language", "fa")

    msg = update.message
    if not msg:
        return

    has_photo = bool(msg.photo)
    text_input = (msg.text or msg.caption or "").strip()

    # اگر نه عکس هست نه متن، کاری نکن
    if not has_photo and not text_input:
        return

    try:
        if has_photo:
            # دریافت URL فایل تلگرام
            try:
                photo = msg.photo[-1]  # بزرگ‌ترین سایز
                file = await context.bot.get_file(photo.file_id)
                if not (TELEGRAM_BOT_TOKEN and getattr(file, "file_path", None)):
                    raise RuntimeError("Telegram file token/path not available")
                image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file.file_path}"
            except Exception:
                log.exception("Failed to resolve Telegram file URL")
                await safe_send(update, context, "⚠️ نتونستم عکس رو بگیرم. دوباره بفرست یا یک متن بنویس.")
                return

            caption_hint = f"\nUser caption: {text_input}" if text_input else ""
            user_content = [
                {"type": "input_text", "text": f"Interface language: {user_lang}.{caption_hint}\nExtract and correct."},
                {"type": "input_image", "image_url": image_url}
            ]
            messages = [
                {"role": "system", "content": SYSTEM_IMAGE},
                {"role": "user", "content": user_content}
            ]
            answer = _retry_chat(messages, temperature=0.2)
        else:
            txt = _truncate(text_input, MAX_INPUT_CHARS)
            prompt = (
                f"Interface language: {user_lang}.\n"
                f"Correct and improve this German text in exam style (B1/B2), "
                f"then provide up to 3 Hinweise and a Persian translation:\n"
                f"{txt}"
            )
            messages = [
                {"role": "system", "content": SYSTEM_TEXT},
                {"role": "user", "content": prompt}
            ]
            answer = _retry_chat(messages, temperature=0.3)

        if not answer:
            answer = "متنی برای نمایش دریافت نشد. لطفاً دوباره ارسال کن."

        await _answer_text(update, context, answer, parse_mode="Markdown")
        await safe_send(update, context, "ادامه می‌دیم؟", reply_markup=_next_actions_kb(user_lang))

    except Exception:
        log.exception("Schreiben failed")
        await safe_send(update, context, "⚠️ خطایی در سرویس تصحیح رخ داد. دوباره تلاش کن؛ اگر ادامه داشت خبر بده.")

@guard()
async def schreiben_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_chat.id, "schreiben")
    lang = get_user(update.effective_chat.id).get("language","fa")
    txt = "متن آلمانی‌ات را بفرست تا تصحیح کنم." if lang=="fa" else "Sende bitte deinen deutschen Text zum Korrigieren."
    await safe_send(update, context, txt)
