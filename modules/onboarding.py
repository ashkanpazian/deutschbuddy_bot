# modules/onboarding.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from utils.memory import set_user, get_user

LANG_FA = "fa"
LANG_DE = "de"

async def greet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # مرحله انتخاب زبان رابط
    kb = [[
        InlineKeyboardButton("Deutsch 🇩🇪", callback_data="lang:de"),
        InlineKeyboardButton("فارسی 🇮🇷",  callback_data="lang:fa"),
    ]]
    text = (
        "Hallo! 👋\nWillkommen beim DeutschBuddy!\n\n"
        "سلام! به دوست آلمانی‌یار خوش اومدی! 🇩🇪\n\n"
        "Möchtest du, dass wir auf Deutsch oder Persisch sprechen?\n"
        "می‌خوای به آلمانی صحبت کنیم یا فارسی؟"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(kb))

async def handle_language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    _, lang = query.data.split(":")
    set_user(chat_id, "language", lang)

    # بعد از انتخاب زبان، خوش‌آمد هوشمند بر اساس داشتن/نداشتن level
    text, kb = post_language_welcome(chat_id, lang)
    await query.edit_message_text(text=text, reply_markup=kb, parse_mode="Markdown")

def post_language_welcome(chat_id: int, lang: str):
    """
    اگر level قبلاً تعیین شده: گزینه‌های ادامه با همان سطح، یا بازآزمایی
    اگر سطح ندارد: پیشنهاد تعیین سطح
    """
    u = get_user(chat_id)
    level = u.get("level")
    goal = u.get("goal") or "lernen"

    if level:
        # کاربر قبلاً تعیین‌سطح شده
        if lang == LANG_DE:
            text = (
                f"✅ *Einstufung vorhanden*\n"
                f"Dein letztes Niveau: **{level}**.\n\n"
                f"Möchtest du mit diesem Niveau fortfahren oder den Test erneut machen?"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("Mit diesem Niveau starten ✅", callback_data="level:continue")],
                [InlineKeyboardButton("Einstufung erneut durchführen 🔁", callback_data="level:redo")],
                [InlineKeyboardButton("Ziel ändern", callback_data=f"goal:set:{goal}")],
                [InlineKeyboardButton("Hauptmenü ⬅️", callback_data="menu:back")]
            ])
        else:
            text = (
                f"✅ *تعیین‌سطح قبلی یافت شد*\n"
                f"سطح آخر شما: **{level}**.\n\n"
                f"می‌خوای با همین سطح ادامه بدی یا دوباره تست بدی؟"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("ادامه با همین سطح ✅", callback_data="level:continue")],
                [InlineKeyboardButton("تعیین سطح دوباره 🔁", callback_data="level:redo")],
                [InlineKeyboardButton("تغییر هدف", callback_data=f"goal:set:{goal}")],
                [InlineKeyboardButton("بازگشت به منو ⬅️", callback_data="menu:back")]
            ])
        return text, kb

    # هنوز تعیین‌سطح نکرده
    if lang == LANG_DE:
        text = (
            "Super! Wir sprechen jetzt auf Deutsch.\n\n"
            "Möchtest du einen kurzen Einstufungstest machen? (nur ~2 Minuten)"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Einstufung starten ✅", callback_data="level:start")],
            [InlineKeyboardButton("Später machen ⏳", callback_data="level:skip")]
        ])
    else:
        text = (
            "عالی! از این به بعد فارسی صحبت می‌کنیم.\n\n"
            "می‌خوای یک تعیین‌سطح خیلی کوتاه انجام بدی؟ (حدود ۲ دقیقه)"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("شروع تعیین سطح ✅", callback_data="level:start")],
            [InlineKeyboardButton("بعداً انجام می‌دم ⏳", callback_data="level:skip")]
        ])
    return text, kb
