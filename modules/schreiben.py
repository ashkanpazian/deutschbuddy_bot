import os
from openai import OpenAI
from telegram import Update
from telegram.ext import ContextTypes
from utils.memory import get_user
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM = "You are a precise German teacher for B1/B2. Reply in the user's interface language, provide corrections, brief reasons (max 3 sentences), then Persian translation."

async def schreiben_correct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    if not text:
        return
    lang = get_user(chat_id).get("language", "fa")
    prompt = f"User language: {lang}. Correct and improve this writing for German exam style:\n{text}"
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],
            temperature=0.3
        )
        answer = resp.choices[0].message.content.strip()
    except Exception as e:
        answer = f"خطا در ارتباط با مدل: {e}"
    await update.message.reply_text(answer, disable_web_page_preview=True)
