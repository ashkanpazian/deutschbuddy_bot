# modules/wortschatz.py
import random
from telegram import Update
from telegram.ext import ContextTypes
from utils.memory import get_user, set_user

# دیتاست بزرگ‌تر + شناسه یکتا
WORDS = [
    {"id": 1, "de": "die Erfahrung", "fa": "تجربه", "lvl": "B1"},
    {"id": 2, "de": "umweltfreundlich", "fa": "سازگار با محیط زیست", "lvl": "B1"},
    {"id": 3, "de": "die Vereinbarung", "fa": "توافق", "lvl": "B2"},
    {"id": 4, "de": "die Voraussetzung", "fa": "پیش‌نیاز", "lvl": "B2"},
    {"id": 5, "de": "sich bewerben", "fa": "درخواست دادن (شغل/تحصیل)", "lvl": "B1"},
    {"id": 6, "de": "die Gelegenheit", "fa": "فرصت", "lvl": "B1"},
    {"id": 7, "de": "nachhaltig", "fa": "پایدار (سازگار با محیط‌زیست)", "lvl": "B2"},
    {"id": 8, "de": "verfügbar", "fa": "در دسترس", "lvl": "B1"},
    {"id": 9, "de": "stattfinden", "fa": "برگزار شدن", "lvl": "B1"},
    {"id":10, "de": "beeinflussen", "fa": "تحت‌تأثیر قرار دادن", "lvl": "B2"},
    {"id":11, "de": "die Fähigkeit", "fa": "توانایی", "lvl": "B1"},
    {"id":12, "de": "verlässlich", "fa": "قابل اتکا", "lvl": "B2"},
    {"id":13, "de": "die Herausforderung", "fa": "چالش", "lvl": "B2"},
    {"id":14, "de": "der Aufenthalt", "fa": "اقامت", "lvl": "B1"},
    {"id":15, "de": "ermöglichen", "fa": "امکان‌پذیر کردن", "lvl": "B2"},
    {"id":16, "de": "vorbereiten", "fa": "آماده کردن/شدن", "lvl": "A2"},
    {"id":17, "de": "die Lösung", "fa": "راه‌حل", "lvl": "A2/B1"},
    {"id":18, "de": "plötzlich", "fa": "ناگهان", "lvl": "A2"},
    {"id":19, "de": "die Erfahrung sammeln", "fa": "کسب تجربه", "lvl": "B1"},
    {"id":20, "de": "sich erinnern (an)", "fa": "به یاد آوردن", "lvl": "A2/B1"},
]

DAILY_COUNT = 8  # تعداد آیتم روزانه

async def vocab_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    seen = set(user.get("seen_words", []))

    # کاندیدها: آیتم‌هایی که هنوز دیده نشده‌اند
    candidates = [w for w in WORDS if w["id"] not in seen]
    if len(candidates) == 0:
        # اگر همه را دیده، ریست کنترل شده (اجازه تکرار پس از چرخه کامل)
        seen = set()
        candidates = WORDS.copy()

    # انتخاب تصادفی بدون تکرار
    pick = random.sample(candidates, k=min(DAILY_COUNT, len(candidates)))

    # ساخت پیام
    lang = user.get("language", "fa")
    header = "📚 واژگان امروز:" if lang == "fa" else "📚 Heutiger Wortschatz:"
    lines = [header]
    for w in pick:
        if lang == "fa":
            lines.append(f"- {w['de']} ({w['lvl']}) — {w['fa']}")
        else:
            lines.append(f"- {w['de']} ({w['lvl']}) — {w['fa']}")

    # بروزرسانی پیشرفت و seen_words
    new_seen = list(seen.union({w["id"] for w in pick}))
    progress = user.get("progress", {})
    progress["wortschatz"] = progress.get("wortschatz", 0) + len(pick)

    set_user(chat_id, "seen_words", new_seen)
    set_user(chat_id, "progress", progress)

    await update.message.reply_text("\n".join(lines))
