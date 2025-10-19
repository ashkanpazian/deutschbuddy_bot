import datetime as dt
from typing import Tuple
from utils.memory import get_user, set_user

WELCOME_BACK_HOURS = 5

def touch_user(chat_id: int, context_name: str = None):
    """آخرین فعالیت و آخرین کانتکست را ثبت می‌کند."""
    now = dt.datetime.utcnow().isoformat()
    set_user(chat_id, "last_activity", now)
    if context_name:
        set_user(chat_id, "last_context", context_name)

def should_show_welcome_back(chat_id: int) -> bool:
    """اگر آخرین فعالیت بیش از WELCOME_BACK_HOURS قبل بوده باشد، True."""
    u = get_user(chat_id)
    last = u.get("last_activity")
    if not last:
        return True
    try:
        prev = dt.datetime.fromisoformat(last)
    except Exception:
        return True
    delta = dt.datetime.utcnow() - prev
    return delta.total_seconds() >= WELCOME_BACK_HOURS * 60
