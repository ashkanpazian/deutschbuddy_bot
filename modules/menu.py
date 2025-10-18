from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from utils.memory import set_user, get_user

def main_menu(lang: str):
    if lang == "de":
        buttons = [
            [InlineKeyboardButton("📅 Heutige Challenge", callback_data="menu:daily"),
             InlineKeyboardButton("📝 Schreiben üben", callback_data="menu:schreiben")],
            [InlineKeyboardButton("📚 Wortschatz", callback_data="menu:wortschatz"),
             InlineKeyboardButton("📖 Grammatik", callback_data="menu:grammar")],
            [InlineKeyboardButton("🈳 Wörterbuch", callback_data="menu:dict")],
            [InlineKeyboardButton("👤 Profil", callback_data="menu:profile")]

        ]
        title = "Hauptmenü"
    else:
        buttons = [
            [InlineKeyboardButton("📅 تمرین امروز", callback_data="menu:daily"),
             InlineKeyboardButton("📝 تمرین Schreiben", callback_data="menu:schreiben")],
            [InlineKeyboardButton("📚 واژگان", callback_data="menu:wortschatz"),
             InlineKeyboardButton("📖 گرامر", callback_data="menu:grammar")],
            [InlineKeyboardButton("🈳 دیکشنری", callback_data="menu:dict")],
            [InlineKeyboardButton("👤 پروفایل", callback_data="menu:profile")]
        ]

        title = "منوی اصلی"
    return title, InlineKeyboardMarkup(buttons)

async def set_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    _, goal = query.data.split(":")
    set_user(chat_id, "goal", goal)
    lang = get_user(chat_id)["language"]
    title, kb = main_menu(lang)
    await query.edit_message_text(text=title, reply_markup=kb)

async def open_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = get_user(chat_id)["language"]
    title, kb = main_menu(lang)
    if update.callback_query:
        await update.callback_query.edit_message_text(text=title, reply_markup=kb)
    else:
        await update.message.reply_text(text=title, reply_markup=kb)

# --- قبلاً اضافه کردیم:
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        chat_id = query.message.chat_id
    else:
        chat_id = update.effective_chat.id

    user = get_user(chat_id)
    lang = user.get("language", "fa")
    level = user.get("level", "—")
    goal = user.get("goal", "—")
    progress = user.get("progress", {"schreiben": 0, "wortschatz": 0})

    if lang == "de":
        text = (
            f"📋 *Dein Profil*\n"
            f"Sprache: Deutsch 🇩🇪\n"
            f"Niveau: {level}\n"
            f"Ziel: {'Lernen 🚀' if goal=='lernen' else 'Wiederholen 🔁'}\n"
            f"Fortschritt:\n"
            f"- Schreiben: {progress.get('schreiben',0)}\n"
            f"- Wortschatz: {progress.get('wortschatz',0)}"
        )
    else:
        text = (
            f"📋 *پروفایل شما*\n"
            f"زبان رابط: {'فارسی 🇮🇷' if lang=='fa' else 'آلمانی 🇩🇪'}\n"
            f"سطح: {level}\n"
            f"هدف: {'یادگیری 🚀' if goal=='lernen' else 'مرور 🔁'}\n"
            f"پیشرفت:\n"
            f"- Schreiben: {progress.get('schreiben',0)} تمرین\n"
            f"- واژگان: {progress.get('wortschatz',0)} تمرین"
        )

    if query:
        await query.edit_message_text(text=text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


async def handle_menu_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    lang = get_user(chat_id)["language"]
    action = query.data.split(":", 1)[1]

    if action == "schreiben":
        msg = "متن آلمانی‌ات را بفرست تا تصحیح کنم." if lang == "fa" else "Schreibe deinen deutschen Text, ich korrigiere ihn."
        await query.edit_message_text(msg)

    elif action == "wortschatz":
        from modules.wortschatz import SAMPLE_WORDS
        lines = ["📚 واژگان امروز:" if lang=="fa" else "📚 Heutiger Wortschatz:"]
        for de, fa, lvl in SAMPLE_WORDS:
            lines.append(f"- {de} ({lvl}) — {fa}")
        await context.bot.send_message(chat_id=chat_id, text="\n".join(lines))

    elif action == "dict":
        msg = ("برای جستجوی کلمه بنویس: /dict Vereinbarung"
               if lang=="fa" else
               "Für ein Wörterbuch-Lookup: /dict Vereinbarung")
        await query.edit_message_text(msg)

    elif action == "grammar":
        msg = ("برای نکتهٔ گرامری بنویس: /grammar Thema (مثلاً /grammar Konjunktiv II)"
               if lang=="fa" else
               "Für einen Grammatik-Tipp: /grammar Thema (z.B. /grammar Konjunktiv II)")
        await query.edit_message_text(msg)

    elif action == "profile":
        await show_profile(update, context)
    elif action == "back":
        title, kb = main_menu(lang)
        await query.edit_message_text(text=title, reply_markup=kb)
    elif action == "daily":
        from modules.daily import daily
        await daily(update, context)

    else:
        await query.edit_message_text("نام دستور منو ناشناخته است.")

async def handle_goal_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    _, _, new_goal = query.data.split(":")
    set_user(chat_id, "goal", new_goal)
    lang = get_user(chat_id)["language"]
    title, kb = main_menu(lang)
    await query.edit_message_text(text=title, reply_markup=kb)
