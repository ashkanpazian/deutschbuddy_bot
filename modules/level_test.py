import json, os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from utils.memory import get_user, set_user
from utils.feedback import level_message

QUEST_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "questions.json")

def load_questions():
    with open(QUEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _idx_to_letter(i: int) -> str:
    return ["A", "B", "C", "D"][i]

async def start_level_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.user_data["level_progress"] = {"q_index": 0, "correct": [], "answers": []}
    await send_next_question(update, context)

async def send_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questions = load_questions()
    prog = context.user_data.get("level_progress", {"q_index": 0})
    i = prog["q_index"]
    if i >= len(questions):
        await finish_level_test(update, context)
        return

    q = questions[i]
    kb = [[InlineKeyboardButton(f"{_idx_to_letter(idx)}. {opt}", callback_data=f"ans:{i}:{idx}")] for idx, opt in enumerate(q["options"])]
    lang = get_user(update.effective_chat.id)["language"]
    pre = "Frage" if lang == "de" else "سؤال"
    text = f"{pre} {i+1}/{len(questions)}:\n{q['question']}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, i_str, opt_str = query.data.split(":")
    i, chosen = int(i_str), int(opt_str)

    questions = load_questions()
    q = questions[i]
    correct = (chosen == q["answer"])
    prog = context.user_data.get("level_progress", {"q_index": 0, "correct": [], "answers": []})
    prog["answers"].append(chosen)
    prog["correct"].append(1 if correct else 0)
    prog["q_index"] = i + 1
    context.user_data["level_progress"] = prog

    mark = "✅" if correct else "❌"
    fb = f"{mark}"
    await query.edit_message_text(text=fb)
    # send next
    await send_next_question(update, context)

async def finish_level_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prog = context.user_data.get("level_progress", {})
    if not prog:
        return
    questions = load_questions()
    score = sum(prog.get("correct", []))
    # naive mapping
    if score <= 1:
        level = "A1"
    elif score == 2:
        level = "A2"
    elif score == 3:
        level = "B1"
    else:
        level = "B2"

    set_user(update.effective_chat.id, "level", level)
    lang = get_user(update.effective_chat.id)["language"]
    msg = level_message(level, lang)
    post = ("می‌خوای با همین سطح ادامه بدیم یا صرفاً مرور کنی؟"
            if lang == "fa"
            else "Möchtest du mit diesem Niveau weiterlernen oder nur wiederholen?")
    kb = [[
        InlineKeyboardButton("ارتقا و یادگیری 🚀" if lang=="fa" else "Lernen 🚀", callback_data="goal:lernen"),
        InlineKeyboardButton("مرور مباحث قبلی 🔁" if lang=="fa" else "Wiederholen 🔁", callback_data="goal:review")
    ]]
    if update.callback_query:
        await update.callback_query.edit_message_text(text=f"{msg}\n\n{post}", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(f"{msg}\n\n{post}", reply_markup=InlineKeyboardMarkup(kb))
