# modules/wortschatz.py
import random
import datetime as dt
import logging
from typing import List, Dict, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ApplicationHandlerStop

from utils.memory import get_user, set_user
from utils.handler_guard import guard
from utils.safe_telegram import safe_send
from utils.session import touch_user

log = logging.getLogger("Wortschatz")

# =========================
# دیتاست واژگان (id, de, fa, lvl)
# =========================
WORDS: List[Dict] = [
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
    {"id":17, "de": "die Lösung", "fa": "راه‌حل", "lvl": "A2"},
    {"id":18, "de": "plötzlich", "fa": "ناگهان", "lvl": "A2"},
    {"id":19, "de": "die Erfahrung sammeln", "fa": "کسب تجربه", "lvl": "B1"},
    {"id":20, "de": "sich erinnern (an)", "fa": "به یاد آوردن", "lvl": "A2"},
]

DAILY_COUNT = 8                # تعداد آیتم روزانه برای نمایش
QUIZ_LEN    = 8                # تعداد سوال کوییز
SRS_STEPS   = [0, 1, 3, 7, 16] # فاصلهٔ روزها برای جعبه‌های مرور (Leitner)

# =========================
# کمک‌کننده‌ها
# =========================
def _today() -> dt.date:
    return dt.date.today()

def _today_iso() -> str:
    return _today().isoformat()

def _user_level(user) -> str:
    lvl = (user.get("level") or "A1").upper()
    return lvl if lvl in {"A1","A2","B1","B2"} else "A1"

def _level_pool(level: str) -> List[Dict]:
    """سطح‌محور با کمی انعطاف (هم‌سطح و یکی بالا/پایین)."""
    neigh = {
        "A1": {"A1","A2"},
        "A2": {"A1","A2","B1"},
        "B1": {"A2","B1","B2"},
        "B2": {"B1","B2"},
    }[level]
    pool = [w for w in WORDS if w["lvl"] in neigh]
    return pool or WORDS

def _seen_set(user) -> set:
    return set(user.get("seen_words", []))

def _get_srs(user) -> Dict[str, Dict]:
    # Map: str(id) -> {"box": int, "due": "YYYY-MM-DD"}
    return user.get("srs", {}) or {}

def _save_srs(chat_id: int, srs: Dict[str, Dict]):
    # پاک‌سازی بیش از حد
    if len(srs) > 2000:
        keys = list(srs.keys())[-2000:]
        srs = {k: srs[k] for k in keys}
    set_user(chat_id, "srs", srs)

def _word_by_id(wid: int) -> Optional[Dict]:
    for w in WORDS:
        if w["id"] == wid:
            return w
    return None

def _due_words(user, on_date: dt.date) -> List[Dict]:
    """واژه‌هایی که موعد مرور دارند (SRS)."""
    srs = _get_srs(user)
    due = []
    for k, v in srs.items():
        try:
            wid = int(k)
            d = dt.date.fromisoformat(v.get("due"))
            if d <= on_date:
                w = _word_by_id(wid)
                if w:
                    due.append(w)
        except Exception:
            continue
    return due

def _mark_seen(chat_id: int, wid: int):
    u = get_user(chat_id)
    seen = list(_seen_set(u))
    if wid not in seen:
        seen.append(wid)
        if len(seen) > 2000:
            seen = seen[-2000:]
        set_user(chat_id, "seen_words", seen)

def _schedule_next_due(curr_box: int) -> Tuple[int, str]:
    nxt_box = min(curr_box + 1, len(SRS_STEPS) - 1)
    days   = SRS_STEPS[nxt_box]
    due    = (_today() + dt.timedelta(days=days)).isoformat()
    return nxt_box, due

def _demote_box(curr_box: int) -> Tuple[int, str]:
    nxt_box = max(0, curr_box - 1)
    days    = SRS_STEPS[nxt_box]
    due     = (_today() + dt.timedelta(days=days)).isoformat()
    return nxt_box, due

def _ensure_quiz_state(context: ContextTypes.DEFAULT_TYPE) -> Dict:
    state = context.user_data.get("vquiz") or {}
    if not state:
        state = {"qs": [], "i": 0, "score": 0}
        context.user_data["vquiz"] = state
    return state

def _kb_start_quiz(lang: str, due_n: int, new_n: int) -> InlineKeyboardMarkup:
    start = "شروع کوییز ✅" if lang == "fa" else "Quiz starten ✅"
    info  = f"🔁 مرور: {due_n} | ✨ جدید: {new_n}"
    back  = "⬅️ بازگشت به منو" if lang == "fa" else "⬅️ Zurück zum Menü"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(start, callback_data="vocab:quiz:start")],
        [InlineKeyboardButton(info, callback_data="noop:vocabinfo")],
        [InlineKeyboardButton(back,  callback_data="menu:back")],
    ])

def _kb_options(opts: List[str], lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"① {opts[0]}", callback_data="vocab:quiz:opt:0")],
        [InlineKeyboardButton(f"② {opts[1]}", callback_data="vocab:quiz:opt:1")],
        [InlineKeyboardButton(f"③ {opts[2]}", callback_data="vocab:quiz:opt:2")],
        [InlineKeyboardButton(f"④ {opts[3]}", callback_data="vocab:quiz:opt:3")],
        [InlineKeyboardButton("⬅️ بازگشت به منو" if lang=="fa" else "⬅️ Zurück zum Menü", callback_data="menu:back")],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_finish(lang: str) -> InlineKeyboardMarkup:
    again = "🔁 یک بسته‌ی دیگر (آزمایشی)" if lang=="fa" else "🔁 Noch ein Paket (Training)"
    back  = "⬅️ بازگشت به منو" if lang=="fa" else "⬅️ Zurück zum Menü"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(again, callback_data="vocab:again")],
        [InlineKeyboardButton(back,  callback_data="menu:back")],
    ])

# =========================
# نمایش روزانه + آماده‌سازی کوییز
# =========================
@guard()
async def vocab_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    1) لیست واژگان روز (مرور موعددار + جدید بدون تکرار)
    2) ذخیرهٔ جلسه برای کوییز
    3) دکمهٔ «شروع کوییز» + «بازگشت»
    """
    touch_user(update.effective_chat.id, "wortschatz")

    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    lang = user.get("language", "fa")
    level = _user_level(user)
    seen  = _seen_set(user)

    # 1) موعددار SRS
    due = _due_words(user, _today())

    # 2) جدیدهای سطح‌محور
    pool = _level_pool(level)
    new_candidates = [w for w in pool if w["id"] not in seen and w not in due]
    random.shuffle(new_candidates)

    picked: List[Dict] = []
    # اولویت: due
    for w in due:
        if len(picked) >= DAILY_COUNT:
            break
        picked.append(w)
    # تکمیل با جدیدها
    for w in new_candidates:
        if len(picked) >= DAILY_COUNT:
            break
        picked.append(w)

    # fallback
    if len(picked) < DAILY_COUNT:
        rest = [w for w in WORDS if w not in picked]
        random.shuffle(rest)
        picked += rest[: (DAILY_COUNT - len(picked))]

    due_n = sum(1 for w in picked if w in due)
    new_n = len(picked) - due_n

    # متن
    header = "📚 واژگان امروز:" if lang == "fa" else "📚 Heutiger Wortschatz:"
    subtitle = f"🔁 مرور: {due_n} | ✨ جدید: {new_n}"
    lines = [header, subtitle, ""]
    for w in picked:
        lines.append(f"- {w['de']} ({w['lvl']}) — {w['fa']}")

    # ذخیرهٔ جلسهٔ امروز
    context.user_data["vocab_today"] = [w["id"] for w in picked]

    # پیشرفت شمارشی (صرفاً نمایش/رِکوردر ساده)
    progress = user.get("progress", {})
    progress["wortschatz"] = progress.get("wortschatz", 0) + len(picked)
    set_user(chat_id, "progress", progress)

    await safe_send(update, context, "\n".join(lines), reply_markup=_kb_start_quiz(lang, due_n, new_n))

# =========================
# کوییز چهارگزینه‌ای DE↔FA
# =========================
def _build_question(word: Dict) -> Dict:
    """
    یک سوال چهارگزینه‌ای می‌سازد.
    جهت به صورت تصادفی: DE→FA یا FA→DE
    """
    direction = random.choice(["DE2FA", "FA2DE"])
    if direction == "DE2FA":
        question = f"معنی درستِ «{word['de']}» را انتخاب کن:"
        correct  = word["fa"]
        distract = [w["fa"] for w in WORDS if w["id"] != word["id"]]
    else:
        question = f"معادل آلمانی «{word['fa']}» کدام است؟"
        correct  = word["de"]
        distract = [w["de"] for w in WORDS if w["id"] != word["id"]]

    random.shuffle(distract)
    # تضمین بدون تکرار
    pool = []
    for d in distract:
        if d not in pool and d != correct:
            pool.append(d)
        if len(pool) == 3:
            break
    options = [correct] + pool
    random.shuffle(options)
    ans_idx = options.index(correct)
    return {"direction": direction, "q": question, "options": options, "ans_idx": ans_idx}

def _prepare_quiz(ids: List[int]) -> List[Dict]:
    sample_ids = ids[:]
    random.shuffle(sample_ids)
    sample_ids = sample_ids[:QUIZ_LEN]
    quiz = []
    for wid in sample_ids:
        w = _word_by_id(wid)
        if not w:
            continue
        q = _build_question(w)
        q["id"] = wid
        quiz.append(q)
    return quiz

@guard()
async def vocab_quiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع کوییز پس از دکمهٔ «شروع کوییز»"""
    touch_user(update.effective_chat.id, "wortschatz")

    user_data = context.user_data
    ids = user_data.get("vocab_today") or []
    if not ids:
        await safe_send(update, context, "اول /wortschatz یا دکمهٔ «📚 واژگان» را بزن تا فهرست امروز آماده شود.")
        return

    state = {"qs": _prepare_quiz(ids), "i": 0, "score": 0}
    user_data["vquiz"] = state

    if not state["qs"]:
        await safe_send(update, context, "امروز موردی برای کوییز پیدا نشد. دوباره تلاش کن.")
        return

    q = state["qs"][0]
    lang = get_user(update.effective_chat.id).get("language", "fa")
    await safe_send(update, context, f"🧠 سوال 1/{len(state['qs'])}\n\n{q['q']}", reply_markup=_kb_options(q["options"], lang))

@guard()
async def vocab_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کال‌بک پاسخ کوییز: pattern → vocab:quiz:opt:<0-3>"""
    touch_user(update.effective_chat.id, "wortschatz")

    cq = update.callback_query
    if not cq or not cq.data or not cq.data.startswith("vocab:quiz:opt:"):
        return

    state = _ensure_quiz_state(context)
    qs = state.get("qs") or []
    i  = state.get("i", 0)
    if i >= len(qs):
        return  # کوییز تمام شده

    q = qs[i]
    idx_str = cq.data.split(":")[-1]
    try:
        chosen = int(idx_str)
    except Exception:
        chosen = -1

    correct = (chosen == q["ans_idx"])
    chat_id = update.effective_chat.id
    u = get_user(chat_id)
    lang = u.get("language", "fa")

    # به‌روزرسانی SRS
    srs = _get_srs(u)
    key = str(q["id"])
    box = int(srs.get(key, {}).get("box", 0))
    if correct:
        state["score"] = int(state.get("score", 0)) + 1
        nbox, due = _schedule_next_due(box)
        srs[key] = {"box": nbox, "due": due}
        _mark_seen(chat_id, q["id"])
    else:
        nbox, due = _demote_box(box)
        srs[key] = {"box": nbox, "due": due}
    _save_srs(chat_id, srs)

    # بازخورد کوتاه
    word = _word_by_id(q["id"])
    if q["direction"] == "DE2FA":
        corr_txt = word["fa"]; pair_txt = f"{word['de']} → {word['fa']}"
    else:
        corr_txt = word["de"]; pair_txt = f"{word['fa']} → {word['de']}"

    fb = ("✅ درست گفتی!" if correct else f"❌ پاسخ درست: *{corr_txt}*") + f"\n↔️ {pair_txt}"
    await safe_send(update, context, fb, parse_mode="Markdown")

    # سؤال بعدی/اتمام
    state["i"] = i + 1
    if state["i"] < len(qs):
        nxt = qs[state["i"]]
        await safe_send(update, context, f"🧠 سوال {state['i']+1}/{len(qs)}\n\n{nxt['q']}", reply_markup=_kb_options(nxt["options"], lang))
    else:
        total = len(qs)
        score = state["score"]
        # پاک کردن state
        context.user_data["vquiz"] = {"qs": [], "i": 0, "score": 0}
        msg = (f"🏁 پایان کوییز!\nامتیاز: {score} از {total}\nمی‌خوای یک بستهٔ دیگر هم تمرین کنی؟")
        if lang != "fa":
            msg = f"🏁 Quiz beendet!\nPunkte: {score} / {total}\nLust auf ein weiteres Paket (Training)?"
        await safe_send(update, context, msg, reply_markup=_kb_finish(lang))

    raise ApplicationHandlerStop

# =========
# بستهٔ تمرینیِ جدید (بدون تغییر شمارنده‌ها)
# =========
@guard()
async def vocab_quiz_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر می‌خواهد یک بستهٔ تمرینی جدید بزند (Training)؛ شمارنده‌های روزانه تغییر نکنند."""
    touch_user(update.effective_chat.id, "wortschatz")

    ids = context.user_data.get("vocab_today") or []
    if not ids:
        await safe_send(update, context, "اول /wortschatz را اجرا کن تا فهرست امروز ساخته شود.")
        return

    state = {"qs": _prepare_quiz(ids), "i": 0, "score": 0}
    context.user_data["vquiz"] = state

    if not state["qs"]:
        await safe_send(update, context, "موردی برای کوییز پیدا نشد. دوباره تلاش کن.")
        return

    q = state["qs"][0]
    lang = get_user(update.effective_chat.id).get("language", "fa")
    await safe_send(update, context, f"🧠 سوال 1/{len(state['qs'])}\n\n{q['q']}", reply_markup=_kb_options(q["options"], lang))
