# modules/home.py
import datetime as dt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.memory import get_user
from utils.session import touch_user, should_show_welcome_back
from utils.safe_telegram import safe_send

def _kb_home(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("▶️ ادامه", callback_data="home:continue")],
        [InlineKeyboardButton("📅 تمرین امروز", callback_data="home:daily"),
         InlineKeyboardButton("📚 واژگان", callback_data="home:wortschatz")],
        [InlineKeyboardButton("📘 گرامر", callback_data="home:grammar"),
         InlineKeyboardButton("✍️ نوشتن", callback_data="home:schreiben")],
        [InlineKeyboardButton("⬅️ منو", callback_data="menu:back")]
    ]
    return InlineKeyboardMarkup(rows)

def _home_summary(u: dict, lang: str) -> str:
    level  = u.get("level") or "A1"
    streak = u.get("daily_streak", 0)
    # شمارش لغات موعددار
    srs = u.get("srs", {}) or {}
    today = dt.date.today()
    due_count = 0
    for v in srs.values():
        try:
            d = dt.date.fromisoformat(v.get("due"))
            if d <= today:
                due_count += 1
        except Exception:
            continue
    # گرامر: prev/current/next خیلی کوتاه
    gp = (u.get("grammar_progress") or {})
    cur_topic = None
    if gp:
        level_g = gp.get("level") or level
        idx = gp.get("index", 0)
        from modules.grammar import GRAMMAR_ROADMAP
        topics = GRAMMAR_ROADMAP.get(level_g, ["Artikel & Plural"])
        cur_topic = topics[min(idx, len(topics)-1)]
    if lang == "fa":
        lines = [
            f"👋 خوش اومدی! (سطح: *{level}*)",
            f"🔥 زنجیرهٔ روزانه: {streak}",
            f"🗓️ لغات موعددار: {due_count}",
        ]
        if cur_topic: lines.append(f"📘 گرامر فعلی: {cur_topic}")
    else:
        lines = [
            f"👋 Willkommen zurück! (Niveau: *{level}*)",
            f"🔥 Tages-Streak: {streak}",
            f"🗓️ Fällige Wörter: {due_count}",
        ]
        if cur_topic: lines.append(f"📘 Aktuelle Grammatik: {cur_topic}")
    return "\n".join(lines)

async def welcome_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """این هندلر با هر پیام کاربر صدا می‌شود (group=0) و اگر وقتش باشد کارت خوش‌آمد را نشان می‌دهد."""
    chat_id = update.effective_chat.id
    u = get_user(chat_id)
    lang = u.get("language", "fa")
    # همیشه لمس کن (برای به‌روز شدن last_activity)
    touch_user(chat_id)
    # فقط اگر زمان گذشته بود کارت را نشان بده
    if should_show_welcome_back(chat_id):
        summary = _home_summary(u, lang)
        header = "🏠 صفحهٔ خانه" if lang == "fa" else "🏠 Startseite"
        await safe_send(update, context, f"{header}\n\n{summary}", reply_markup=_kb_home(lang), parse_mode="Markdown")

# کال‌بک‌های دکمه‌های خانه
async def home_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    chat_id = update.effective_chat.id
    u = get_user(chat_id)
    lang = u.get("language","fa")
    # لمس
    touch_user(chat_id)

    if data == "home:continue":
        # ادامه از آخرین بافت
        ctx = u.get("last_context")
        if ctx == "daily":
            from modules.daily import daily
            await daily(update, context)
        elif ctx == "wortschatz":
            from modules.wortschatz import vocab_daily
            await vocab_daily(update, context)
        elif ctx == "grammar":
            from modules.grammar import grammar_tip
            await grammar_tip(update, context)
        elif ctx == "schreiben":
            txt = "متن آلمانی‌ات را بفرست تا تصحیح کنم." if lang=="fa" else "Sende deinen deutschen Text zur Korrektur."
            await safe_send(update, context, txt)
        else:
            # اگر چیزی ثبت نشده بود → منو
            from modules.menu import open_menu
            await open_menu(update, context)

    elif data == "home:daily":
        from modules.daily import daily
        await daily(update, context)

    elif data == "home:wortschatz":
        from modules.wortschatz import vocab_daily
        await vocab_daily(update, context)

    elif data == "home:grammar":
        from modules.grammar import grammar_tip
        await grammar_tip(update, context)

    elif data == "home:schreiben":
        txt = "متن آلمانی‌ات را بفرست تا تصحیح کنم." if lang=="fa" else "Sende deinen deutschen Text zur Korrektur."
        await safe_send(update, context, txt)
