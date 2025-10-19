# modules/menu.py
import logging
from typing import Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from utils.memory import set_user, get_user
from utils.handler_guard import guard
from utils.safe_telegram import safe_send
from utils.session import touch_user

log = logging.getLogger("Menu")

# ========================
# UI helpers
# ========================
def _main_menu_kb(lang: str) -> Tuple[str, InlineKeyboardMarkup]:
    if lang == "de":
        buttons = [
            [InlineKeyboardButton("📅 Heutige Challenge", callback_data="menu:daily"),
             InlineKeyboardButton("📝 Schreiben üben",   callback_data="menu:schreiben")],
            [InlineKeyboardButton("📚 Wortschatz",       callback_data="menu:wortschatz"),
             InlineKeyboardButton("📖 Grammatik",        callback_data="menu:grammar")],
            [InlineKeyboardButton("🈳 Wörterbuch",       callback_data="menu:dict")],
            [InlineKeyboardButton("👤 Profil",           callback_data="menu:profile")],
        ]
        title = "Hauptmenü"
    else:
        buttons = [
            [InlineKeyboardButton("📅 تمرین امروز",     callback_data="menu:daily"),
             InlineKeyboardButton("📝 تمرین Schreiben", callback_data="menu:schreiben")],
            [InlineKeyboardButton("📚 واژگان",          callback_data="menu:wortschatz"),
             InlineKeyboardButton("📖 گرامر",           callback_data="menu:grammar")],
            [InlineKeyboardButton("🈳 دیکشنری",         callback_data="menu:dict")],
            [InlineKeyboardButton("👤 پروفایل",         callback_data="menu:profile")],
        ]
        title = "منوی اصلی"
    return title, InlineKeyboardMarkup(buttons)

def _back_only_kb(lang: str) -> InlineKeyboardMarkup:
    label = "⬅️ بازگشت به منو" if lang == "fa" else "⬅️ Zurück zum Menü"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="menu:back")]])

def _schreiben_prompt(lang: str) -> str:
    return ("متن آلمانی‌ات را بفرست تا تصحیح کنم. (می‌تونی عکس هم بفرستی) ✍️"
            if lang == "fa" else
            "Sende deinen deutschen Text (oder ein Foto) zur Korrektur. ✍️")

def _dict_hint(lang: str) -> str:
    return ("برای جستجوی کلمه بنویس: `/dict Vereinbarung` یا `/dict توافق`\n"
            "بهت معنی‌ها + یک مثال آلمانی با ترجمه می‌دم."
            if lang == "fa" else
            "Für ein Wörterbuch-Lookup: `/dict Vereinbarung` oder `/dict توافق`.\n"
            "Du bekommst Bedeutungen + einen deutschen Beispielsatz mit FA-Übersetzung.")

def _grammar_hint(lang: str) -> str:
    return ("برای نکتهٔ گرامری بنویس: `/grammar Thema` (مثلاً `/grammar Konjunktiv II`)\n"
            "یا از مسیر گرامری سطحت در منو جلو برو."
            if lang == "fa" else
            "Für einen Grammatik-Tipp: `/grammar Thema` (z. B. `/grammar Konjunktiv II`).\n"
            "Oder folge dem stufengerechten Pfad im Menü.")

# ========================
# Public API (handlers)
# ========================

@guard()
async def open_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش/به‌روزرسانی منوی اصلی."""
    chat_id = update.effective_chat.id
    touch_user(chat_id, "menu")

    lang = get_user(chat_id).get("language", "fa")
    title, kb = _main_menu_kb(lang)

    await safe_send(update, context, title, reply_markup=kb)

@guard()
async def set_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم هدف lern/review و بازگشت به منو."""
    query = update.callback_query
    if not query or not query.data.startswith("goal:"):
        return

    await query.answer()
    chat_id = query.message.chat_id
    touch_user(chat_id, "menu")

    _, goal = query.data.split(":")
    set_user(chat_id, "goal", goal)

    lang = get_user(chat_id).get("language", "fa")
    title, kb = _main_menu_kb(lang)
    await safe_send(update, context, title, reply_markup=kb)

# ---- Profile (ارتقاء یافته در پاسخ قبلی) ----
# اگر نسخهٔ پیشرفتهٔ show_profile / profile_refresh را قبلاً در همین فایل ساختی،
# همان‌ها را نگه دار. اگر نه، حداقل نسخهٔ سادهٔ زیر دکمهٔ بازگشت دارد:

@guard()
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پروفایل + بازگشت به منو (نسخهٔ ساده؛ می‌تونی با نسخهٔ پیشرفته جایگزین کنی)."""
    chat_id = update.effective_chat.id
    touch_user(chat_id, "profile")

    u = get_user(chat_id)
    lang = u.get("language", "fa")
    level = u.get("level", "—")
    goal = u.get("goal", "lernen")
    prog = u.get("progress", {"schreiben": 0, "wortschatz": 0})
    streak = u.get("daily_streak", 0)

    if lang == "de":
        text = (
            "👤 *Dein Profil*\n"
            f"- Niveau: **{level}**\n"
            f"- Ziel: **{'Lernen 🚀' if goal=='lernen' else 'Wiederholen 🔁'}**\n"
            f"- Tages-Streak: **{streak}**\n"
            f"- Fortschritt: Schreiben={prog.get('schreiben',0)}, Wortschatz={prog.get('wortschatz',0)}"
        )
    else:
        text = (
            "👤 *پروفایل شما*\n"
            f"- سطح: **{level}**\n"
            f"- هدف: **{'یادگیری 🚀' if goal=='lernen' else 'مرور 🔁'}**\n"
            f"- زنجیرهٔ روزانه: **{streak}**\n"
            f"- پیشرفت: Schreiben={prog.get('schreiben',0)}، واژگان={prog.get('wortschatz',0)}"
        )

    await safe_send(update, context, text, parse_mode="Markdown", reply_markup=_back_only_kb(lang))

# ---- Router for menu buttons ----
@guard()
async def handle_menu_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """روتِ دکمه‌های منو → هر بخش را فراخوانی می‌کند و همیشه راه بازگشت دارد."""
    query = update.callback_query
    if not query or not query.data.startswith("menu:"):
        return

    await query.answer()
    chat_id = query.message.chat_id
    u = get_user(chat_id)
    lang = u.get("language", "fa")
    action = query.data.split(":", 1)[1]

    touch_user(chat_id, action)

    # --- Routing ---
    if action == "daily":
        from modules.daily import daily
        await daily(update, context)
        return

    if action == "wortschatz":
        from modules.wortschatz import vocab_daily
        await vocab_daily(update, context)
        return

    if action == "schreiben":
        await safe_send(update, context, _schreiben_prompt(lang), reply_markup=_back_only_kb(lang))
        return

    if action == "grammar":
        # راهنمای کوتاه + بازگشت
        await safe_send(update, context, _grammar_hint(lang), parse_mode="Markdown", reply_markup=_back_only_kb(lang))
        return

    if action == "dict":
        await safe_send(update, context, _dict_hint(lang), parse_mode="Markdown", reply_markup=_back_only_kb(lang))
        return

    if action == "profile":
        await show_profile(update, context)
        return

    if action == "back":
        title, kb = _main_menu_kb(lang)
        await safe_send(update, context, title, reply_markup=kb)
        return

    # ناشناخته
    await safe_send(update, context, "❓ دستور ناشناخته است.", reply_markup=_back_only_kb(lang))
