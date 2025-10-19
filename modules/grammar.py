# modules/grammar.py
import os
import logging
from typing import Dict, List, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from dotenv import load_dotenv

from utils.memory import get_user, set_user
from utils.handler_guard import guard
from utils.safe_telegram import safe_send
from utils.session import touch_user
from utils.ui import back_menu_kb

load_dotenv()
log = logging.getLogger("Grammar")

# مسیر گرامر سطح‌محور
GRAMMAR_ROADMAP: Dict[str, List[str]] = {
    "A1": [
        "Artikel & Plural (der/die/das)",
        "Personalpronomen & sein/haben",
        "Präsens Grundform (Verbzweit)",
        "Fragesätze & W-Fragen",
        "Modalverben (können/müssen/…)",
        "Akkusativ vs. Nominativ (Grundlagen)",
    ],
    "A2": [
        "Trennbare/Untrennbare Verben",
        "Perfekt mit haben/sein",
        "Dativ-Grundlagen (mit/bei/zu …)",
        "Nebensätze mit weil/dass",
        "Steigerung der Adjektive (Komparativ/Superlativ)",
    ],
    "B1": [
        "Konjunktiv II (Höflichkeit & Irreales)",
        "Passiv Präsens/Präteritum",
        "Relativsätze (der/die/das …)",
        "Temporal-Sätze (wenn/als/nachdem)",
        "Wortstellung im Nebensatz (Verb am Ende)",
    ],
    "B2": [
        "Konjunktiv I/II in der indirekten Rede",
        "Partizipialkonstruktionen",
        "Nominalisierung von Verben/Adjektiven",
        "Präpositionen mit fester Rektion (B2-typisch)",
        "Verbklammer & erweiterte Satzklammer",
    ],
}

SYSTEM = (
    "You are a patient, structured German grammar tutor. "
    "Return output in this 4-part format, concise and exam-oriented:\n"
    "1) عنوان (DE) + ترجمه کوتاه فارسی\n"
    "2) نکات کلیدی (۳ Bullet) به آلمانی + ترجمه کوتاه فارسی\n"
    "3) 3 مثال کوتاه آلمانی با ترجمه‌ی فارسی\n"
    "4) تمرین خیلی کوتاه (۳ سؤال) با پاسخ‌های مدل در پایان پیام\n"
)

def _user_level(u) -> str:
    lvl = (u.get("level") or "A1").upper()
    return lvl if lvl in GRAMMAR_ROADMAP else "A1"

def _get_progress(u) -> Dict:
    p = u.get("grammar_progress") or {}
    if "level" not in p:
        p["level"] = _user_level(u)
    if "index" not in p:
        p["index"] = 0
    if "history" not in p:
        p["history"] = []
    return p

def _current_triplet(level: str, index: int) -> Tuple[Optional[str], str, Optional[str]]:
    topics = GRAMMAR_ROADMAP[level]
    prev_t = topics[index - 1] if index - 1 >= 0 else None
    cur_t  = topics[index] if 0 <= index < len(topics) else topics[-1]
    next_t = topics[index + 1] if index + 1 < len(topics) else None
    return prev_t, cur_t, next_t

def _nav_kb(lang: str, prev_t: Optional[str], next_t: Optional[str]) -> InlineKeyboardMarkup:
    rows = []
    nav = []
    if prev_t:
        nav.append(InlineKeyboardButton("◀️ قبلی" if lang=="fa" else "◀️ Zurück", callback_data="grammar:prev"))
    if next_t:
        nav.append(InlineKeyboardButton("بعدی ▶️" if lang=="fa" else "Weiter ▶️", callback_data="grammar:next"))
    if nav:
        rows.append(nav)
    # دکمه بازگشت همیشه هست
    rows.append([InlineKeyboardButton("⬅️ بازگشت به منو" if lang=="fa" else "⬅️ Zurück zum Menü", callback_data="menu:back")])
    return InlineKeyboardMarkup(rows)

def _header(lang: str, level: str, prev_t, cur_t, next_t) -> str:
    if lang == "fa":
        lines = ["📘 *مسیر گرامر سطح* " + level]
        if prev_t: lines.append(f"- قبلی: _{prev_t}_")
        lines.append(f"- فعلی: **{cur_t}**")
        if next_t: lines.append(f"- بعدی: _{next_t}_")
        return "\n".join(lines)
    else:
        lines = [f"📘 *Grammatik-Pfad Stufe {level}*"]
        if prev_t: lines.append(f"- Vorher: _{prev_t}_")
        lines.append(f"- Aktuell: **{cur_t}**")
        if next_t: lines.append(f"- Nächste: _{next_t}_")
        return "\n".join(lines)

from utils.ai_client import chat_completion

def _ask_grammar(topic: str, lang_ui: str) -> str:
    user_prompt = (
        f"Interface language: {lang_ui}. "
        f"Explain the grammar topic '{topic}' with DE+FA as specified in the system message."
    )
    return chat_completion(
        [{"role":"system","content":SYSTEM},{"role":"user","content":user_prompt}],
        temperature=0.3
    )

@guard()
async def grammar_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_chat.id, "grammar")
    text = (update.message.text or "").strip() if update.message else ""
    override = text.replace("/grammar", "", 1).strip()

    u = get_user(update.effective_chat.id)
    lang = u.get("language", "fa")
    progress = _get_progress(u)
    level = progress["level"]
    index = progress["index"]

    if override:
        header = _header(lang, level, None, override, None)
        body = _ask_grammar(override, lang)
        await safe_send(update, context, f"{header}\n\n{body}", reply_markup=_nav_kb(lang, None, None), parse_mode="Markdown")
        hist = progress.get("history", [])
        hist.append((level, override))
        progress["history"] = hist[-20:]
        set_user(update.effective_chat.id, "grammar_progress", progress)
        return

    prev_t, cur_t, next_t = _current_triplet(level, index)
    header = _header(lang, level, prev_t, cur_t, next_t)
    body = _ask_grammar(cur_t, lang)
    hist = progress.get("history", [])
    if not hist or hist[-1] != (level, cur_t):
        hist.append((level, cur_t))
        progress["history"] = hist[-20:]
    set_user(update.effective_chat.id, "grammar_progress", progress)
    await safe_send(update, context, f"{header}\n\n{body}", reply_markup=_nav_kb(lang, prev_t, next_t), parse_mode="Markdown")

@guard()
async def grammar_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_chat.id, "grammar")
    chat_id = update.effective_chat.id
    u = get_user(chat_id); lang = u.get("language","fa")
    p = _get_progress(u); level = p["level"]; index = p["index"]
    topics = GRAMMAR_ROADMAP[level]
    if index + 1 < len(topics):
        p["index"] = index + 1
        set_user(chat_id, "grammar_progress", p)
    prev_t, cur_t, next_t = _current_triplet(level, p["index"])
    header = _header(lang, level, prev_t, cur_t, next_t)
    body = _ask_grammar(cur_t, lang)
    await safe_send(update, context, f"{header}\n\n{body}", reply_markup=_nav_kb(lang, prev_t, next_t), parse_mode="Markdown")

@guard()
async def grammar_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_chat.id, "grammar")
    chat_id = update.effective_chat.id
    u = get_user(chat_id); lang = u.get("language","fa")
    p = _get_progress(u); level = p["level"]; index = p["index"]
    if index - 1 >= 0:
        p["index"] = index - 1
        set_user(chat_id, "grammar_progress", p)
    prev_t, cur_t, next_t = _current_triplet(level, p["index"])
    header = _header(lang, level, prev_t, cur_t, next_t)
    body = _ask_grammar(cur_t, lang)
    await safe_send(update, context, f"{header}\n\n{body}", reply_markup=_nav_kb(lang, prev_t, next_t), parse_mode="Markdown")
