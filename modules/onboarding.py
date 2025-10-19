# modules/onboarding.py
import logging
from typing import Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from utils.memory import set_user, get_user
from utils.handler_guard import guard
from utils.safe_telegram import safe_send

LANG_FA = "fa"
LANG_DE = "de"

log = logging.getLogger("Onboarding")

# ---------------------------
# کمکی‌ها: کیبوردها
# ---------------------------
def _kb_language_and_quickstart() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Deutsch 🇩🇪", callback_data="lang:de"),
         InlineKeyboardButton("فارسی 🇮🇷",  callback_data="lang:fa")],
        [InlineKeyboardButton("🚀 شروع سریع", callback_data="onboard:start")]
    ])

def _kb_level_continue(lang: str, goal: str) -> InlineKeyboardMarkup:
    if lang == LANG_DE:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("Mit diesem Niveau starten ✅", callback_data="level:continue")],
            [InlineKeyboardButton("Einstufung erneut 🔁", callback_data="level:redo")],
            [InlineKeyboardButton("Ziel ändern", callback_data=f"goal:set:{goal}")],
            [InlineKeyboardButton("Hauptmenü ⬅️", callback_data="menu:back")],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("ادامه با همین سطح ✅", callback_data="level:continue")],
            [InlineKeyboardButton("تعیین سطح دوباره 🔁", callback_data="level:redo")],
            [InlineKeyboardButton("تغییر هدف", callback_data=f"goal:set:{goal}")],
            [InlineKeyboardButton("بازگشت به منو ⬅️", callback_data="menu:back")],
        ])

def _kb_level_offer(lang: str) -> InlineKeyboardMarkup:
    if lang == LANG_DE:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("Einstufung starten ✅", callback_data="level:start")],
            [InlineKeyboardButton("Später machen ⏳", callback_data="level:skip")],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("شروع تعیین سطح ✅", callback_data="level:start")],
            [InlineKeyboardButton("بعداً انجام می‌دم ⏳", callback_data="level:skip")],
        ])

# ---------------------------
# خوشامد پس از انتخاب زبان / وضعیت کاربر
# ---------------------------
def post_language_welcome_text_kb(chat_id: int, lang: str) -> Tuple[str, InlineKeyboardMarkup]:
    """
    اگر level قبلاً تعیین شده: ادامه با همان سطح / بازآزمون
    اگر سطح ندارد: پیشنهاد تعیین سطح کوتاه
    """
    u = get_user(chat_id)
    level = u.get("level")
    goal = u.get("goal") or "lernen"

    if level:
        if lang == LANG_DE:
            text = (f"✅ *Einstufung vorhanden*\n"
                    f"Dein letztes Niveau: **{level}**.\n\n"
                    f"Weiter mit diesem Niveau oder den Test neu machen?")
        else:
            text = (f"✅ *تعیین‌سطح قبلی یافت شد*\n"
                    f"سطح آخر شما: **{level}**.\n\n"
                    f"می‌خوای با همین سطح ادامه بدی یا دوباره تست بدی؟")
        return text, _kb_level_continue(lang, goal)

    # هنوز تعیین‌سطح نشده
    if lang == LANG_DE:
        text = ("عالی! از این به بعد آلمانی صحبت می‌کنیم.\n\n"
                "Möchtest du einen kurzen Einstufungstest machen؟ (nur ~2 Minuten)")
    else:
        text = ("عالی! از این به بعد فارسی صحبت می‌کنیم.\n\n"
                "می‌خوای یک تعیین‌سطح خیلی کوتاه انجام بدی؟ (حدود ۲ دقیقه)")
    return text, _kb_level_offer(lang)

# ---------------------------
# /start با پشتیبانی دیپ‌لینک
# ---------------------------
@guard()
async def greet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start [fa|de|quick_lernen|quick_review]
    - اگر پارامتر زبان یا هدف بیاد، همون ابتدا تنظیم می‌شه.
    - اگر کاربر قبلاً سطح داشته باشد، همان اول ادامه/بازآزمون پیشنهاد می‌شود.
    - در غیر این صورت، انتخاب زبان + «شروع سریع».
    """
    chat_id = update.effective_chat.id
    user = get_user(chat_id)

    # پردازش پارامترهای دیپ‌لینک (مثلاً ?start=fa)
    args = context.args or []
    if args:
        token = (args[0] or "").strip().lower()
        if token in {LANG_FA, LANG_DE}:
            set_user(chat_id, "language", token)
        elif token == "quick_lernen":
            set_user(chat_id, "goal", "lernen")
        elif token == "quick_review":
            set_user(chat_id, "goal", "review")

    lang = (get_user(chat_id).get("language") or LANG_FA)

    # اگر سطح از قبل وجود دارد → پیام ادامه/بازآزمون
    if user.get("level"):
        text, kb = post_language_welcome_text_kb(chat_id, lang)
        await safe_send(update, context, text, reply_markup=kb, parse_mode="Markdown")
        return

    # خوشامد دوزبانه + انتخاب زبان + شروع سریع
    text = (
        "Hallo! 👋\nWillkommen bei *DeutschBuddy*!\n\n"
        "سلام! به *DeutschBuddy* خوش اومدی! 🇩🇪\n\n"
        "Möchtest du auf Deutsch oder Persisch geführt werden?\n"
        "می‌خوای به آلمانی راهنمایی بشی یا فارسی؟\n\n"
        "می‌تونی از «🚀 شروع سریع» هم استفاده کنی."
    )
    await safe_send(update, context, text, reply_markup=_kb_language_and_quickstart(), parse_mode="Markdown")

# ---------------------------
# انتخاب زبان از دکمه
# ---------------------------
@guard()
async def handle_language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    chat_id = update.effective_chat.id
    data = (query.data if query else "").strip()

    # data مثل lang:de یا lang:fa
    try:
        _, lang = data.split(":")
    except Exception:
        lang = LANG_FA

    set_user(chat_id, "language", lang)
    text, kb = post_language_welcome_text_kb(chat_id, lang)
    await safe_send(update, context, text, reply_markup=kb, parse_mode="Markdown")

# ---------------------------
# دکمه «🚀 شروع سریع»
# ---------------------------
@guard()
async def onboarding_quickstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    - اگر زبان مشخص نشده باشد → فارسی پیش‌فرض.
    - اگر goal مشخص نشده باشد → سوال هدف (lernen/review) در همان جریان منو.
    - اگر سطح ندارد → مستقیم تعیین‌سطح.
    - در غیر این صورت → منوی اصلی.
    """
    chat_id = update.effective_chat.id
    u = get_user(chat_id)
    if "language" not in u:
        set_user(chat_id, "language", LANG_FA)
    lang = get_user(chat_id).get("language", LANG_FA)

    # اگر هدف هنوز تعیین نشده، به جریان تنظیم هدف بفرست
    if "goal" not in u:
        if lang == LANG_FA:
            txt = "هدفت چیه؟"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("یادگیری 🔥", callback_data="goal:set:lernen"),
                 InlineKeyboardButton("مرور ♻️",   callback_data="goal:set:review")]
            ])
        else:
            txt = "Dein Ziel?"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("Lernen 🔥",   callback_data="goal:set:lernen"),
                 InlineKeyboardButton("Wiederholen ♻️", callback_data="goal:set:review")]
            ])
        await safe_send(update, context, txt, reply_markup=kb)
        return

    # اگر سطح ندارد → تعیین‌سطح
    if not u.get("level"):
        from modules.level_test import start_level_test
        await start_level_test(update, context)
        return

    # وگرنه → منوی اصلی
    from modules.menu import open_menu
    await open_menu(update, context)
