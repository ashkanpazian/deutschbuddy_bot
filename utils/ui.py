from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def back_menu_kb(lang: str) -> InlineKeyboardMarkup:
    label = "⬅️ بازگشت به منو" if lang == "fa" else "⬅️ Zurück zum Menü"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="menu:back")]])

def again_or_back_kb(lang: str, again_cb: str, again_label_fa: str, again_label_de: str) -> InlineKeyboardMarkup:
    again = again_label_fa if lang == "fa" else again_label_de
    back  = "⬅️ بازگشت به منو" if lang == "fa" else "⬅️ Zurück zum Menü"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(again, callback_data=again_cb)],
        [InlineKeyboardButton(back,  callback_data="menu:back")]
    ])
