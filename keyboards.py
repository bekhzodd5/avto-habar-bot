import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import PREMIUM_EMOJIS, ADMIN_ID

def main_menu_kb(is_logged_in: bool = False, is_broadcasting: bool = False, selected_count: int = 0, interval: int = 2, user_id: int = None):
    kb = []
    if not is_logged_in:
        kb.append([
            InlineKeyboardButton(
                text=" Akkaunt ulash", 
                callback_data="menu_connect_account",
                icon_custom_emoji_id=PREMIUM_EMOJIS["link"],
                style="success"
            ),
            InlineKeyboardButton(
                text=" Bot haqida", 
                callback_data="menu_about",
                icon_custom_emoji_id=PREMIUM_EMOJIS["doc"],
                style="primary"
            )
        ])
    else:
        # 1-qator: Boshlash/To'xtatish va Post kiritish (2 ta)
        status_btn = " To'xtatish" if is_broadcasting else " Boshlash"
        status_action = "broadcast_stop" if is_broadcasting else "broadcast_start"
        status_icon = PREMIUM_EMOJIS["cross"] if is_broadcasting else PREMIUM_EMOJIS["rocket"]
        status_style = "danger" if is_broadcasting else "success"
        
        kb.append([
            InlineKeyboardButton(
                text=status_btn, 
                callback_data=status_action,
                icon_custom_emoji_id=status_icon,
                style=status_style
            ),
            InlineKeyboardButton(
                text=" Post (Xabar)", 
                callback_data="menu_set_message",
                icon_custom_emoji_id=PREMIUM_EMOJIS["write"],
                style="primary"
            )
        ])
            
        # 2-qator: Hikoya (Story) & Kanallar (2 ta)
        kb.append([
            InlineKeyboardButton(
                text=" Hikoya (Story)", 
                callback_data="menu_set_story",
                icon_custom_emoji_id=PREMIUM_EMOJIS["tabs"],
                style="primary"
            ),
            InlineKeyboardButton(
                text=f" Kanallar ({selected_count})", 
                callback_data="menu_folders",
                icon_custom_emoji_id=PREMIUM_EMOJIS["folder"],
                style="primary"
            )
        ])
        
        # 3-qator: Vaqt & Holat (2 ta)
        kb.append([
            InlineKeyboardButton(
                text=f" Vaqt ({interval} min)", 
                callback_data="menu_interval",
                icon_custom_emoji_id=PREMIUM_EMOJIS["timer"],
                style="primary"
            ),
            InlineKeyboardButton(
                text=" Holat & Statistika", 
                callback_data="menu_status",
                icon_custom_emoji_id=PREMIUM_EMOJIS["stats"],
                style="primary"
            )
        ])
        
        # 4-qator: Akkaunt & Bot haqida (2 ta)
        kb.append([
            InlineKeyboardButton(
                text=" Akkaunt", 
                callback_data="menu_account",
                icon_custom_emoji_id=PREMIUM_EMOJIS["user"],
                style="primary"
            ),
            InlineKeyboardButton(
                text=" Bot haqida", 
                callback_data="menu_about",
                icon_custom_emoji_id=PREMIUM_EMOJIS["doc"],
                style="primary"
            )
        ])
        
        # 5-qator: Agar admin bo'lsa (2 ta)
        if user_id and user_id == ADMIN_ID:
            kb.append([
                InlineKeyboardButton(
                    text=" Admin Panel",
                    callback_data="menu_admin_panel",
                    icon_custom_emoji_id=PREMIUM_EMOJIS["lock"],
                    style="danger"
                ),
                InlineKeyboardButton(
                    text=" Chiqish", 
                    callback_data="account_logout",
                    icon_custom_emoji_id=PREMIUM_EMOJIS["logout"],
                    style="danger"
                )
            ])
            
    return InlineKeyboardMarkup(inline_keyboard=kb)

def login_method_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=" Telefon raqam", 
                callback_data="login_method_phone",
                icon_custom_emoji_id=PREMIUM_EMOJIS["phone"],
                style="primary"
            ),
            InlineKeyboardButton(
                text=" QR-kod orqali", 
                callback_data="login_method_qr",
                icon_custom_emoji_id=PREMIUM_EMOJIS["camera"],
                style="primary"
            )
        ],
        [
            InlineKeyboardButton(
                text=" Ortga", 
                callback_data="menu_back_main",
                icon_custom_emoji_id=PREMIUM_EMOJIS["back"],
                style="danger"
            )
        ]
    ])

def interval_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 minut", callback_data="set_interval_1", style="primary"),
            InlineKeyboardButton(text="2 minut", callback_data="set_interval_2", style="primary")
        ],
        [
            InlineKeyboardButton(text="3 minut", callback_data="set_interval_3", style="primary"),
            InlineKeyboardButton(text="4 minut", callback_data="set_interval_4", style="primary")
        ],
        [
            InlineKeyboardButton(text="5 minut", callback_data="set_interval_5", style="primary"),
            InlineKeyboardButton(text="10 minut", callback_data="set_interval_10", style="primary")
        ],
        [
            InlineKeyboardButton(text="15 minut", callback_data="set_interval_15", style="primary"),
            InlineKeyboardButton(text="30 minut", callback_data="set_interval_30", style="primary")
        ],
        [
            InlineKeyboardButton(text="60 minut", callback_data="set_interval_60", style="primary"),
            InlineKeyboardButton(
                text=" Asosiy menyu", 
                callback_data="menu_back_main",
                icon_custom_emoji_id=PREMIUM_EMOJIS["back"],
                style="danger"
            )
        ]
    ])

def folders_menu_kb(folders: list, all_channels: list, selected_ids: set):
    kb = []
    
    # Papkalarni 2 tadan qilib joylashtirish
    folder_btns = []
    for f in folders:
        f_ids = set(f.get("channel_ids", []))
        is_selected = len(f_ids) > 0 and f_ids.issubset(selected_ids)
        title = f.get("title", "Papka")
        count = f.get("count", len(f_ids))
        
        style_color = "success" if is_selected else "primary"
        icon_id = PREMIUM_EMOJIS["check"] if is_selected else PREMIUM_EMOJIS["folder"]
        
        folder_btns.append(
            InlineKeyboardButton(
                text=f" {title} ({count})",
                callback_data=f"toggle_folder_{f['id']}",
                icon_custom_emoji_id=icon_id,
                style=style_color
            )
        )
    
    for i in range(0, len(folder_btns), 2):
        kb.append(folder_btns[i:i+2])
    
    # Barcha kanallar va Saqlash (2 ta)
    total_count = len(all_channels)
    kb.append([
        InlineKeyboardButton(
            text=f" Barchasi ({total_count}) ➡️",
            callback_data="menu_channels_0",
            icon_custom_emoji_id=PREMIUM_EMOJIS["clipboard"],
            style="primary"
        ),
        InlineKeyboardButton(
            text=" Saqlash", 
            callback_data="save_channels_confirm",
            icon_custom_emoji_id=PREMIUM_EMOJIS["save"],
            style="success"
        )
    ])
    
    # Hammasi va Tozalash (2 ta)
    kb.append([
        InlineKeyboardButton(
            text=" Hammasi", 
            callback_data="select_all_global",
            icon_custom_emoji_id=PREMIUM_EMOJIS["check"],
            style="success"
        ),
        InlineKeyboardButton(
            text=" Tozalash", 
            callback_data="deselect_all_global",
            icon_custom_emoji_id=PREMIUM_EMOJIS["cross"],
            style="danger"
        )
    ])
    
    # Asosiy menyu
    kb.append([
        InlineKeyboardButton(
            text=" Asosiy menyu", 
            callback_data="menu_back_main",
            icon_custom_emoji_id=PREMIUM_EMOJIS["back"],
            style="danger"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

def channels_paginated_kb(all_channels: list, selected_ids: set, page: int = 0, per_page: int = 6):
    total_pages = max(1, math.ceil(len(all_channels) / per_page))
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_channels = all_channels[start_idx:end_idx]
    
    ch_btns = []
    for ch in current_channels:
        ch_id = ch["id"]
        is_selected = ch_id in selected_ids
        title = ch.get("title", "Nomsiz")
        if len(title) > 18:
            title = title[:15] + "..."
            
        style_color = "success" if is_selected else "primary"
        icon_id = PREMIUM_EMOJIS["check"] if is_selected else PREMIUM_EMOJIS["checkbox_off"]
        
        ch_btns.append(InlineKeyboardButton(
            text=f" {title}",
            callback_data=f"toggle_ch_{ch_id}_{page}",
            icon_custom_emoji_id=icon_id,
            style=style_color
        ))
        
    kb = []
    for i in range(0, len(ch_btns), 2):
        kb.append(ch_btns[i:i+2])
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"menu_channels_{page-1}", style="primary"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="noop", style="primary"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"menu_channels_{page+1}", style="primary"))
    if nav_row:
        kb.append(nav_row)
        
    kb.append([
        InlineKeyboardButton(
            text=" Papkalar", 
            callback_data="menu_folders",
            icon_custom_emoji_id=PREMIUM_EMOJIS["folder"],
            style="danger"
        ),
        InlineKeyboardButton(
            text=" Saqlash", 
            callback_data="save_channels_confirm",
            icon_custom_emoji_id=PREMIUM_EMOJIS["save"],
            style="success"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

def cancel_action_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=" Bekor qilish", 
                callback_data="action_cancel",
                icon_custom_emoji_id=PREMIUM_EMOJIS["cross"],
                style="danger"
            )
        ]
    ])

def account_settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=" Akkauntni uzish", 
                callback_data="account_logout",
                icon_custom_emoji_id=PREMIUM_EMOJIS["logout"],
                style="danger"
            ),
            InlineKeyboardButton(
                text=" Asosiy menyu", 
                callback_data="menu_back_main",
                icon_custom_emoji_id=PREMIUM_EMOJIS["back"],
                style="primary"
            )
        ]
    ])
