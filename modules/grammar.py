# modules/grammar.py
import os, logging
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.memory import get_user

log = logging.getLogger("Grammar")
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM = (
    "You are a patient, structured German grammar tutor. "
    "Return output in this 4-part format, concise and exam-oriented:\n"
    "1) عنوان (DE) + ترجمه کوتاه فارسی\n"
    "2) نکات کلیدی (۳ Bullet) به آلمانی + ترجمه کوتاه فارسی\n"
    "3) 3 مثال کوتاه آلمانی با ترجمه‌ی فارسی\n"
    "4) تمرین خیلی کوتاه (۳ سؤال) با پاسخ‌های مدل در پایان پیام\n"
)

def back_menu_keyboard(lang: str):
    label = "بازگشت به منو ⬅️" if lang == "fa" else "Zurück zum Menü ⬅️"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="menu:back")]])

async def grammar_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # دستور /grammar Konjunktiv II
    text = (update.message.text or "").strip()
    topic = text.replace("/grammar", "").strip()
    if not topic:
        topic = "Konjunktiv II (Höflichkeit)"

    chat_id = update.effective_chat.id
    lang = get_user(chat_id).get("language", "fa")

    user_prompt = (
        f"Interface language: {lang}. "
        f"Explain the grammar topic '{topic}' with DE+FA as specified in the system message."
    )
    try:
        log.info(f"Calling OpenAI grammar: {topic}")
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role":"system","content":SYSTEM},
                      {"role":"user","content":user_prompt}],
            temperature=0.3
        )
        ans = resp.choices[0].message.content.strip()
    except Exception as e:
        log.exception("OpenAI error in grammar_tip")
        ans = f"خطا در ارتباط با مدل: {e}"

    await update.message.reply_text(ans, disable_web_page_preview=True, reply_markup=back_menu_keyboard(lang))
