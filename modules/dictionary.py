# modules/dictionary.py
import re
import json
import logging
from typing import Tuple, Optional, Dict, Any, List

from telegram import Update
from telegram.ext import ContextTypes

from utils.handler_guard import guard
from utils.safe_telegram import safe_send
from utils.ui import again_or_back_kb
from utils.memory import get_user
from utils.session import touch_user
from utils.ai_client import chat_completion  # مرکزی: ریترا‌ی + بک‌آف

log = logging.getLogger("Dictionary")

SYSTEM = (
    "You are a precise DE↔FA lexicographer. Always respond as strict, valid JSON (UTF-8, no code fences). "
    "Schema:\n"
    "{"
    "  'headword': str, 'lang': 'DE'|'FA', 'pos': str, 'gender': str|null, "
    "  'plural_or_forms': str|null, 'pronunciation': str|null, "
    "  'senses': [ {'gloss': str, 'translations': [str], 'example_de': str, 'example_fa': str} ]"
    "}\n"
    "Guidelines:\n"
    "- If input is German, translate to FA; if input is Persian, translate to DE.\n"
    "- Provide 2–4 concise senses where possible.\n"
    "- Include part of speech (pos), gender for nouns (m/f/n) when applicable; forms briefly for verbs/nouns.\n"
    "- Include one short German example with a natural FA translation for each sense.\n"
    "- Output must be pure JSON. No markdown, no extra text."
)

def _detect_lang(q: str) -> str:
    """Return 'DE' if latin-heavy, 'FA' if Persian/Arabic script present."""
    return "FA" if re.search(r"[آاآبپتثجچحخدذرزژسشصضطظعغفقکگلمنوهیۀء]", q) else "DE"

def _build_user_prompt(q: str, q_lang: str) -> str:
    if q_lang == "DE":
        return (
            f"Lookup headword: {q}\n"
            f"Input language: DE. Output JSON in the schema above, with Persian translations in 'translations'. "
            f"For verbs include basic forms; for nouns include gender and plural when relevant."
        )
    else:
        return (
            f"Lookup headword: {q}\n"
            f"Input language: FA. Output JSON in the schema above, with German equivalents in 'translations'. "
            f"Choose natural DE equivalents; keep senses concise."
        )

def _coerce_json(raw: str) -> Optional[Dict[str, Any]]:
    """سعی می‌کنه خروجی مدل رو به JSONِ معتبر تبدیل کنه."""
    raw = (raw or "").strip()
    # مستقیم
    try:
        return json.loads(raw)
    except Exception:
        pass
    # استخراج آخرین بلاک JSON
    m = re.search(r"\{[\s\S]*\}\s*$", raw)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None

def _format_entry(d: Dict[str, Any]) -> str:
    head = d.get("headword") or "-"
    lang = d.get("lang") or "-"
    pos  = d.get("pos") or "-"
    gen  = d.get("gender")
    forms = d.get("plural_or_forms")
    pron = d.get("pronunciation")
    senses: List[Dict[str, Any]] = d.get("senses") or []

    flag = "🇩🇪" if lang == "DE" else "🇮🇷"
    lines = [f"🔎 *{head}* {flag}"]
    meta_bits = [pos]
    if gen:   meta_bits.append(gen)
    if forms: meta_bits.append(forms)
    if pron:  meta_bits.append(f"/{pron}/")
    if any(meta_bits):
        lines.append("— " + " · ".join(meta_bits))

    if senses:
        lines.append("\n**معانی / Senses:**")
        for i, s in enumerate(senses, 1):
            gloss = s.get("gloss") or "-"
            trans = s.get("translations") or []
            ex_de = s.get("example_de") or ""
            ex_fa = s.get("example_fa") or ""
            lines.append(f"{i}) {gloss}")
            if trans:
                lines.append(f"   ↔️ {', '.join(trans)}")
            if ex_de and ex_fa:
                lines.append(f"   📝 {ex_de}")
                lines.append(f"   🔁 {ex_fa}")
    return "\n".join(lines)

@guard()
async def lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /dict <word>
    - خروجی تمیز با مثال‌ها
    - دکمهٔ «🔎 جستجوی کلمهٔ دیگر» + «⬅️ بازگشت به منو»
    - ثبت context برای Welcomeback
    """
    touch_user(update.effective_chat.id, "dict")

    text = (update.message.text or "").strip()
    if not text:
        return
    q = text.replace("/dict", "", 1).strip()
    if not q:
        await safe_send(update, context, "کلمه‌ای بعد از /dict وارد کن. مثال: `/dict Vereinbarung`", parse_mode="Markdown")
        return

    q_lang = _detect_lang(q)
    user_prompt = _build_user_prompt(q, q_lang)

    try:
        raw = chat_completion(
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.2,
        )
        data = _coerce_json(raw)
        if isinstance(data, dict):
            out = _format_entry(data)
        else:
            log.warning("Dictionary: non-JSON response; sending raw text.")
            out = raw or "پاسخی دریافت نشد."

        lang = get_user(update.effective_chat.id).get("language", "fa")
        kb = again_or_back_kb(
            lang,
            again_cb="dict:again",
            again_label_fa="🔎 جستجوی کلمهٔ دیگر",
            again_label_de="🔎 Neues Wort suchen",
        )

        # ارسال ایمن و چندبخشی در صورت نیاز
        await safe_send(update, context, out, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=kb)

    except Exception:
        log.exception("Lookup failed for query: %s", q)
        await safe_send(update, context, "⚠️ خطا در دیکشنری. دوباره تلاش کن؛ اگر ادامه داشت اطلاع بده.")

# کال‌بک «جستجوی بعدی»
@guard()
async def dict_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_chat.id, "dict")
    lang = get_user(update.effective_chat.id).get("language", "fa")
    txt = (
        "کلمهٔ جدیدت را با /dict بنویس (مثلاً `/dict Vereinbarung`)."
        if lang == "fa"
        else "Sende ein neues Wort mit /dict (z. B. `/dict Vereinbarung`)."
    )
    await safe_send(update, context, txt, parse_mode="Markdown")
