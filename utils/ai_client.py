import os, time, random, logging
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
log = logging.getLogger("AI")

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def chat_completion(messages, temperature=0.3, max_attempts=3):

    attempt = 0
    while True:
        try:
            resp = _client.chat.completions.create(
                model=_MODEL,
                messages=messages,
                temperature=temperature
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            attempt += 1
            if attempt >= max_attempts:
                log.exception(f"OpenAI failed after {attempt} attempts")
                raise
            base = min(10, 2 ** attempt)
            jitter = random.uniform(0.2, 0.5) * base
            wait = base + jitter
            log.warning(f"OpenAI error: {e}. retrying in {wait:.1f}s (attempt {attempt})")
            time.sleep(wait)
