# modules/daily.py
import random
import datetime as dt
import logging
from typing import Dict, List, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ApplicationHandlerStop

from utils.memory import get_user, set_user
from utils.handler_guard import guard
from utils.safe_telegram import safe_send
from utils.session import touch_user

log = logging.getLogger("Daily")

# =========================
# داده‌های تمرین سطح‌محور
# =========================

# واژگان سطح‌محور: (DE, FA, level)
VOCAB_BANK: List[Tuple[str, str, str]] = [
    # A1
    ("das Haus", "خانه", "A1"),
    ("die Schule", "مدرسه", "A1"),
    ("der Freund", "دوست (مذکر)", "A1"),
    ("die Stadt", "شهر", "A1"),
    ("essen", "خوردن", "A1"),
    ("gehen", "رفتن", "A1"),
    # A2
    ("die Erfahrung", "تجربه", "A2"),
    ("billig", "ارزان", "A2"),
    ("ständig", "دائماً، پیوسته", "A2"),
    ("sich erinnern", "به خاطر آوردن / یادآوری کردن", "A2"),
    # B1
    ("stattfinden", "برگزار شدن", "B1"),
    ("umweltfreundlich", "سازگار با محیط زیست", "B1"),
    ("die Fähigkeit", "توانایی", "B1"),
    ("verlässlich", "قابل‌اتکا", "B1"),
    # B2
    ("die Vereinbarung", "توافق", "B2"),
    ("ermöglichen", "امکان‌پذیر کردن", "B2"),
    ("nachhaltig", "پایدار (دوام‌دار/سازگار با محیط زیست)", "B2"),
    ("die Voraussetzung", "پیش‌نیاز، شرط لازم", "B2"),
]

# جملات جای‌خالی سطح‌محور: (prompt, answer, level)
GAP_BANK: List[Tuple[str, str, str]] = [
    # A1
    ("Ich ____ müde.", "bin", "A1"),
    ("Wir ____ nach Hause.", "gehen", "A1"),
    ("Er ____ ein Brot.", "isst", "A1"),
    # A2
    ("Ich ____ mich an deinen Namen.", "erinnere", "A2"),
    ("Das ist nicht teuer, es ist ____.", "billig", "A2"),
    # B1
    ("Das Konzert ____ morgen statt.", "findet", "B1"),
    ("Sie ist sehr ____ und kommt nie zu spät.", "verlässlich", "B1"),
    # B2
    ("Digitale Tools ____ flexibles Lernen.", "ermöglichen", "B2"),
    ("Eine wichtige ____ für den Job ist Teamfähigkeit.", "Voraussetzung", "B2"),
]

# =========================
# ابزارهای داخلی
# =========================

def _today_iso() -> str:
    return dt.date.today().isoformat()

def _yesterday_iso() -> str:
    return (dt.date.today() - dt.timedelta(days=1)).isoformat()

def _user_level(u) -> str:
    lvl = (u.get("level") or "A1").upper()
    return lvl if lvl in {"A1", "A2", "B1", "B2"} else "A1"

def _back_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    label = "⬅️ بازگشت به منو" if lang == "fa" else "⬅️ Zurück zum Menü"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="menu:back")]])

def _choices_keyboard(options: List[str], lang: str) -> InlineKeyboardMarkup:
    # دکمه‌های چهارگزینه‌ای + بازگشت
    rows = [
        [InlineKeyboardButton(f"① {options[0]}", callback_data="daily:opt:0")],
        [InlineKeyboardButton(f"② {options[1]}", callback_data="daily:opt:1")],
        [InlineKeyboardButton(f"③ {options[2]}", callback_data="daily:opt:2")],
        [InlineKeyboardButton(f"④ {options[3]}", callback_data="daily:opt:3")],
        [InlineKeyboardButton("⬅️ بازگشت به منو" if lang=="fa" else "⬅️ Zurück zum Menü", callback_data="menu:back")],
    ]
    return InlineKeyboardMarkup(rows)

def _again_or_back_kb(lang: str) -> InlineKeyboardMarkup:
    again = "🔁 یک تمرین دیگر (آزمایشی)" if lang == "fa" else "🔁 Noch eine Übung (Training)"
    back  = "⬅️ بازگشت به منو" if lang == "fa" else "⬅️ Zurück zum Menü"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(again, callback_data="daily:again")],
        [InlineKeyboardButton(back,  callback_data="menu:back")],
    ])

def _filter_by_level(items: List[Tuple], level: str) -> List[Tuple]:
    # اجازه سطح همجوار
    prio_levels = {
        "A1": {"A1", "A2"},
        "A2": {"A1", "A2", "B1"},
        "B1": {"A2", "B1", "B2"},
        "B2": {"B1", "B2"},
    }[level]
    pool = [x for x in items if x[-1] in prio_levels]
    return pool or items

def _get_seen_words(u) -> set:
    return set(u.get("seen_words") or [])

def _mark_seen(chat_id: int, de_word: str):
    u = get_user(chat_id)
    seen = list(_get_seen_words(u))
    if de_word not in seen:
        seen.append(de_word)
        if len(seen) > 500:
            seen = seen[-500:]
        set_user(chat_id, "seen_words", seen)

def _pick_new_vocab_for_user(u) -> Tuple[str, str, str]:
    """انتخاب واژهٔ جدید مناسب سطح و بدون تکرار."""
    level = _user_level(u)
    pool = _filter_by_level(VOCAB_BANK, level)
    seen = _get_seen_words(u)
    fresh = [x for x in pool if x[0] not in seen]
    picks = fresh or pool  # اگر همه دیده شدند، اجازهٔ تکرار کنترل‌شده
    de, fa, lv = random.choice(picks)
    return de, fa, lv

def _build_mcq(u) -> Dict:
    """تمرین چهارگزینه‌ای واژگان: DE → معنی فارسی (۴ گزینه)."""
    de, fa, lv = _pick_new_vocab_for_user(u)
    distractors = [b for a, b, _ in VOCAB_BANK if b != fa]
    random.shuffle(distractors)
    opts = [fa] + distractors[:3]
    random.shuffle(opts)
    correct_idx = opts.index(fa)
    return {
        "mode": "mcq",
        "level": lv,
        "question": f"🔤 *Wortschatz* — واژهٔ امروز:\n\n**{de}**\n\nمعنی درست را انتخاب کن:",
        "options": opts,
        "answer_index": correct_idx,
        "meta": {"de": de, "fa": fa}
    }

def _build_gap(u) -> Dict:
    """تمرین جای‌خالی: پاسخ نوشتاری یک‌کلمه‌ای."""
    level = _user_level(u)
    pool = _filter_by_level(GAP_BANK, level)
    prompt, answer, lv = random.choice(pool)
    return {
        "mode": "gap",
        "level": lv,
        "question": f"✍️ *Satzergänzung* — جای خالی را پر کن:\n\n« {prompt} »\n\nپاسخ را همین‌جا بنویس.",
        "answer_text": answer.lower().strip(),
        "meta": {}
    }

def _update_streak(user: Dict) -> int:
    tday = _today_iso()
    last = user.get("last_daily")
    streak = user.get("daily_streak", 0)
    if last == _yesterday_iso():
        streak += 1
    elif last == tday:
        return streak
    else:
        streak = 1
    return streak

# =========================
# هندلرهای بات
# =========================

@guard()
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    شروع تمرین روزانه:
    - یک‌بار در روز (اما کاربر می‌تواند تمرینِ «آزمایشی» اضافه بگیرد)
    - تولید MCQ یا GAP بر اساس سطح
    - ذخیرهٔ تمرین در context.user_data["daily_current"]
    """
    touch_user(update.effective_chat.id, "daily")

    chat_id = update.effective_chat.id
    u = get_user(chat_id)
    lang = u.get("language", "fa")
    tday = _today_iso()

    # آیا این نوبت «اضافی/آزمایشی» است؟
    extra_mode = context.user_data.get("daily_mode") == "extra"

    # جلوگیری از چندبارگی رسمی در یک روز (اما اجازهٔ تمرین آزمایشی)
    if u.get("last_daily") == tday and not extra_mode and context.user_data.get("daily_current") is None:
        msg = "✅ تمرین امروز انجام شده.\nمی‌خوای یک تمرین آزمایشی هم انجام بدی؟" if lang == "fa" \
              else "✅ Die heutige Übung ist erledigt.\nMöchtest du eine zusätzliche Trainingsübung?"
        await safe_send(update, context, msg, reply_markup=_again_or_back_kb(lang))
        return

    # انتخاب نوع تمرین
    mode_pick = "mcq" if random.random() < 0.6 else "gap"
    task = _build_mcq(u) if mode_pick == "mcq" else _build_gap(u)

    # ذخیرهٔ تمرین جاری
    context.user_data["daily_current"] = task

    # فقط در حالت «رسمی»، streak و last_daily را آپدیت کن
    if not extra_mode:
        streak = _update_streak(u)
        set_user(chat_id, "daily_streak", streak)
        set_user(chat_id, "last_daily", tday)
    else:
        streak = u.get("daily_streak", 0)

    footer = f"\n\n🔥 زنجیرهٔ روزانه: {streak}" if lang == "fa" else f"\n\n🔥 Tages-Streak: {streak}"

    # ارسال تمرین
    if task["mode"] == "mcq":
        kb = _choices_keyboard(task["options"], lang)
        await safe_send(update, context, f"📅 *تمرین امروز*\n\n{task['question']}{footer}", reply_markup=kb, parse_mode="Markdown")
    else:
        await safe_send(update, context, f"📅 *تمرین امروز*\n\n{task['question']}{footer}", reply_markup=_back_menu_keyboard(lang), parse_mode="Markdown")

@guard()
async def daily_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر یک تمرین آزمایشی (اضافی) می‌خواهد—استریک/تاریخ دست نمی‌خورند."""
    touch_user(update.effective_chat.id, "daily")
    context.user_data["daily_mode"] = "extra"
    context.user_data["daily_current"] = None  # هرچه بود پاک شود
    await daily(update, context)

@guard()
async def daily_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    پاسخ به چهارگزینه‌ای (CallbackQuery: daily:opt:<i>)
    """
    cq = update.callback_query
    if not cq or not cq.data or not cq.data.startswith("daily:opt:"):
        return
    task = context.user_data.get("daily_current")
    if not task or task.get("mode") != "mcq":
        return

    idx_str = cq.data.split(":")[-1]
    try:
        chosen = int(idx_str)
    except Exception:
        chosen = -1

    correct = (chosen == task.get("answer_index"))
    u = get_user(update.effective_chat.id)
    lang = u.get("language", "fa")

    de = task["meta"].get("de", "")
    fa = task["meta"].get("fa", "")

    # ثبت واژهٔ دیده‌شده
    if de:
        _mark_seen(update.effective_chat.id, de)

    if correct:
        msg = "✅ درست گفتی! عالی بود." if lang == "fa" else "✅ Super, richtig!"
    else:
        correct_txt = task["options"][task["answer_index"]]
        msg = (f"❌ پاسخ دقیق‌تر: *{correct_txt}*\n↔️ {de} → {fa}") if lang == "fa" \
              else (f"❌ Korrekte Antwort: *{correct_txt}*\n↔️ {de} → {fa}")

    # بعد از پاسخ، مسیر ادامه داشته باشد
    await safe_send(update, context, msg, parse_mode="Markdown", reply_markup=_again_or_back_kb(lang))

    # پاک کردن تمرین جاری و ریستِ حالت اضافه
    context.user_data["daily_current"] = None
    context.user_data.pop("daily_mode", None)

    # جلوگیری از عبور به هندلرهای بعدی
    raise ApplicationHandlerStop

@guard()
async def daily_check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    پاسخ متنی (برای GAP). اگر تمرین جاری GAP نبود، اجازه بده سایر هندلرها کارشان را بکنند.
    """
    touch_user(update.effective_chat.id, "daily")
    task = context.user_data.get("daily_current")
    if not task or task.get("mode") != "gap":
        return  # به سایر هندلرها واگذار کن

    user_ans = (update.message.text or "").strip().lower()
    expected = task.get("answer_text", "").lower()
    u = get_user(update.effective_chat.id)
    lang = u.get("language", "fa")

    if user_ans == expected:
        msg = "✅ عالی! پاسخ درست بود." if lang == "fa" else "✅ Super! Richtig beantwortet."
    else:
        msg = f"❌ پاسخ دقیق‌تر: *{expected}*" if lang == "fa" else f"❌ Korrekte Antwort: *{expected}*"

    # بعد از پاسخ، مسیر ادامه داشته باشد
    await safe_send(update, context, msg, parse_mode="Markdown", reply_markup=_again_or_back_kb(lang))

    # اتمام تمرین جاری و ریستِ حالت اضافه
    context.user_data["daily_current"] = None
    context.user_data.pop("daily_mode", None)

    # جلوگیری از ادامهٔ زنجیره
    raise ApplicationHandlerStop
