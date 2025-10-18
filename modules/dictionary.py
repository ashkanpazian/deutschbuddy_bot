import os, logging
from openai import OpenAI
from telegram import Update
from telegram.ext import ContextTypes
from dotenv import load_dotenv

log = logging.getLogger("Dictionary")
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM = "You are a DE↔FA dictionary assistant: provide concise meanings, example sentence DE with FA translation, and part of speech."

async def lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return
    q = text.replace("/dict", "").strip()
    if not q:
        await update.message.reply_text("کلمه‌ای بعد از /dict وارد کن. مثلا: /dict Vereinbarung")
        return
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":SYSTEM},
                      {"role":"user","content":f"Lookup: {q} → meanings in FA and brief info"}],
            temperature=0.2
        )
        ans = resp.choices[0].message.content.strip()
    except Exception as e:
        ans = f"خطا در ارتباط با مدل: {e}"
    await update.message.reply_text(ans, disable_web_page_preview=True)
