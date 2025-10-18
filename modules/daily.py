# modules/daily.py
import random
import datetime as dt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ApplicationHandlerStop
from utils.memory import get_user, set_user

# بانک نمونه‌ها (بعداً می‌تونی گسترش بدی)
VOCAB_POOL = [
    ("die Vereinbarung", "توافق", "B2"),
    ("verlässlich", "قابل اتکا", "B2"),
    ("die Fähigkeit", "توانایی", "B1"),
    ("umweltfreundlich", "سازگار با محیط زیست", "B1"),
    ("stattfinden", "برگزار شدن", "B1"),
    ("ermöglichen", "امکان‌پذیر کردن", "B2"),
]

SENTENCE_GAPS = [
    ("Ich ____ seit zwei Jahren Deutsch.", "lerne"),
    ("Wir ____ am Wochenende ins Kino.", "gehen"),
    ("Das Konzert ____ morgen statt.", "findet"),
]

def today_iso():
    return dt.date.today().isoformat()

def back_menu_keyboard(lang: str):
    label = "بازگشت به منو ⬅️" if lang == "fa" else "Zurück zum Menü ⬅️"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="menu:back")]])

async def _send_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode="Markdown"):
    """
    ارسال سازگار:
    - اگر از Callback آمده‌ایم (update.callback_query موجود است)، از send_message استفاده کن.
    - اگر پیام معمولی است، reply_text.
    """
    chat_id = update.effective_chat.id
    if update.callback_query:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تولید 'تمرین امروز': 1 واژه + 1 جمله جای‌خالی.
    یک‌بار در روز. پاسخ درست/غلط در daily_check_answer بررسی می‌شود.
    """
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    lang = user.get("language", "fa")

    tday = today_iso()
    if user.get("last_daily") == tday:
        msg = "✅ تمرین امروز را انجام داده‌ای.\nفردا برمی‌گردم با تمرین جدید!" if lang=="fa" \
              else "✅ Deine heutige Challenge ist erledigt. Morgen gibt es eine neue!"
        await _send_text(update, context, msg, reply_markup=back_menu_keyboard(lang))
        return

    w = random.choice(VOCAB_POOL)
    g = random.choice(SENTENCE_GAPS)

    if lang == "fa":
        header = "📅 چالش امروز"
        body = (
            f"1) واژهٔ امروز: *{w[0]}* — {w[1]} ({w[2]})\n"
            f"2) جمله‌سازی کوتاه:\n"
            f"   « {g[0]} »\n"
            f"   پاسخ را همین‌جا بنویس."
        )
    else:
        header = "📅 Heutige Challenge"
        body = (
            f"1) Heutiges Wort: *{w[0]}* — {w[1]} ({w[2]})\n"
            f"2) Satzergänzung:\n"
            f"   « {g[0]} »\n"
            f"   Antworte hier mit dem fehlenden Wort."
        )

    # انتظار پاسخ را در user_data ذخیره می‌کنیم
    context.user_data["daily_expected"] = g[1].lower().strip()

    # streak به‌روز شود
    last = user.get("last_daily")
    streak = user.get("daily_streak", 0)
    if last:
        yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        if last == yesterday:
            streak += 1
        elif last != tday:
            streak = 1
    else:
        streak = 1

    set_user(chat_id, "last_daily", tday)
    set_user(chat_id, "daily_streak", streak)

    footer = f"\n\n🔥 زنجیرهٔ روزانه: {streak}" if lang=="fa" else f"\n\n🔥 Tages-Streak: {streak}"
    await _send_text(update, context, f"{header}\n\n{body}{footer}", reply_markup=back_menu_keyboard(lang))

async def daily_check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expected = context.user_data.get("daily_expected")
    if not expected:
        return

    ans = (update.message.text or "").strip().lower()
    expected = expected.lower().strip()
    lang = get_user(update.effective_chat.id).get("language", "fa")

    if ans == expected:
        msg = "✅ عالی! پاسخ درست بود." if lang=="fa" else "✅ Super! Richtig beantwortet."
    else:
        msg = f"❌ پاسخ دقیق‌تر: *{expected}*" if lang=="fa" else f"❌ Korrekte Antwort: *{expected}*"

    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=back_menu_keyboard(lang))
    context.user_data.pop("daily_expected", None)
    raise ApplicationHandlerStop
