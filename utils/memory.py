# utils/memory.py
import json, os
from typing import Dict, Any

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "user_state.json")

default_state = {
    "language": "fa",        # 'fa' or 'de'
    "level": None,           # 'A1'..'B2'
    "goal": None,            # 'lernen' or 'review'
    "progress": {
        "schreiben": 0,
        "wortschatz": 0
    },
    "seen_words": []         # لیست شناسه واژگان نشان‌داده‌شده برای جلوگیری از تکرار
}

def _load_all() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_all(data: Dict[str, Any]):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(chat_id: int) -> Dict[str, Any]:
    data = _load_all()
    u = data.get(str(chat_id))
    if not u:
        return json.loads(json.dumps(default_state))  # deep copy
    # تضمین backward compatibility
    for k,v in default_state.items():
        if k not in u:
            u[k] = json.loads(json.dumps(v))
    return u

def set_user(chat_id: int, key: str, value):
    data = _load_all()
    u = data.get(str(chat_id), json.loads(json.dumps(default_state)))
    u[key] = value
    data[str(chat_id)] = u
    _save_all(data)

def set_user_bulk(chat_id: int, updates: Dict[str, Any]):
    data = _load_all()
    u = data.get(str(chat_id), json.loads(json.dumps(default_state)))
    for k,v in updates.items():
        u[k] = v
    data[str(chat_id)] = u
    _save_all(data)
