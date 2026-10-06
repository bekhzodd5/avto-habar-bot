import sys
import os

# =====================================================================
# HOSTING UCHUN: Asosiy yo'lni to'g'rilash (Linux / Windows / Hosting)
# =====================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
try:
    os.chdir(BASE_DIR)
except Exception:
    pass

# =====================================================================
# HOSTING UCHUN: Yetishmayotgan kutubxonalarni avtomatik o'rnatish
# =====================================================================
def _auto_install_dependencies():
    packages = {
        "aiogram": "aiogram>=3.30.0",
        "telethon": "telethon>=1.44.0",
        "qrcode": "qrcode[pil]",
        "PIL": "Pillow"
    }
    import subprocess
    for mod, pkg in packages.items():
        try:
            __import__(mod)
        except ImportError:
            try:
                print(f"📦 [HOSTING] {pkg} kutubxonasi o'rnatilmoqda...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])
            except Exception as e:
                print(f"⚠️ O'rnatishda xatolik ({pkg}): {e}")

_auto_install_dependencies()

import asyncio
import logging
import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_ID, emo, PREMIUM_EMOJIS
import database as db
import userbot_manager as ub
import keyboards as kb

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Vaqtinchalik kanallar va papkalar keshi (user_id: {"folders": list, "channels": list, "selected_ids": set})
channels_cache = {}

# FSM holatlari
class AuthStates(StatesGroup):
    waiting_phone = State()
    waiting_sms_code = State()
    waiting_2fa_password = State()

class BroadcastStates(StatesGroup):
    waiting_post_message = State()
    waiting_story_message = State()

# --- YORDAMCHI FUNKSIYALAR ---

async def get_main_menu_text_and_kb(user_id: int):
    user = db.get_user(user_id)
    is_logged_in = bool(user and user.get("session_string"))
    
    if not is_logged_in:
        text = (
            f"{emo('wave')} <b>Assalomu alaykum!</b>\n\n"
            f"Ushbu bot orqali siz o'z Telegram akkauntingizni ulab, belgilangan "
            f"kanallar va {emo('folder')} <b>Papkalar (Folders)</b>ga istalgan xabar, {emo('tabs')} <b>Hikoya (Story)</b> yoki postlarni "
            f"(shu jumladan {emo('star')} <b>Telegram Premium emojilar</b> bilan) avtomatik ravishda belgilangan vaqt oralig'ida tarqatishingiz mumkin.\n\n"
            f"{emo('rocket')} <i>Boshlash uchun akkauntingizni ulang:</i>"
        )
        return text, kb.main_menu_kb(is_logged_in=False, user_id=user_id)
    
    is_broadcasting = bool(user.get("is_broadcasting"))
    selected_channels = user.get("selected_channels", [])
    interval = user.get("interval_minutes", 2)
    name = user.get("first_name") or "Foydalanuvchi"
    phone = user.get("phone") or "Noma'lum"
    b_type = user.get("broadcast_type", "post")
    
    status_text = f"{emo('dot_green')} <b>Faol (Yuborilmoqda {emo('rocket')})</b>" if is_broadcasting else f"{emo('cross')} <b>To'xtatilgan</b>"
    
    if user.get("broadcast_forward_msg_id") or user.get("broadcast_msg_text") or user.get("broadcast_story_url"):
        if b_type == "story":
            has_msg = f"{emo('check')} 📖 Hikoya (Story)"
        else:
            has_msg = f"{emo('check')} ✍️ Post (Xabar)"
    else:
        has_msg = f"{emo('cross')} Kiritilmagan"
    
    text = (
        f"{emo('wave')} <b>Xush kelibsiz, {name}!</b>\n\n"
        f"{emo('phone')} <b>Akkaunt:</b> <code>{phone}</code>\n"
        f"{emo('rocket')} <b>Holat:</b> {status_text}\n"
        f"{emo('speaker')} <b>Tanlangan kanallar:</b> <b>{len(selected_channels)}</b> ta\n"
        f"{emo('timer')} <b>Vaqt oralig'i:</b> <b>{interval}</b> minut\n"
        f"{emo('tabs')} <b>Tarqatish turi:</b> {has_msg}\n\n"
        "<i>Kerakli amalni tanlang:</i>"
    )
    return text, kb.main_menu_kb(
        is_logged_in=True,
        is_broadcasting=is_broadcasting,
        selected_count=len(selected_channels),
        interval=interval,
        user_id=user_id
    )

# --- START VA ASOSIY MENYU ---

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    text, markup = await get_main_menu_text_and_kb(message.from_user.id)
    await message.answer(text, reply_markup=markup)

@dp.callback_query(F.data == "menu_back_main")
async def cb_back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = await get_main_menu_text_and_kb(call.from_user.id)
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()

@dp.callback_query(F.data == "action_cancel")
async def cb_action_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await ub.cancel_login(call.from_user.id)
    text, markup = await get_main_menu_text_and_kb(call.from_user.id)
    await call.message.edit_text(f"{emo('cross')} Amal bekor qilindi.\n\n" + text, reply_markup=markup)
    await call.answer()

@dp.callback_query(F.data == "menu_about")
async def cb_about(call: CallbackQuery):
    about_text = (
        f"{emo('doc')} <b>Bot haqida:</b>\n\n"
        "Bu bot sizning Telegram akkauntingiz orqali kanallarga xabarlar va **Hikoyalar (Stories)**ni "
        "avtomatlashtirilgan tarzda tarqatish (avto-reklama) uchun mo'ljallangan.\n\n"
        "<b>Imkoniyatlari:</b>\n"
        f"• {emo('phone')} Telefon raqam yoki {emo('camera')} QR-kod orqali oson ulanish\n"
        f"• {emo('lock')} 2-bosqichli parol (2FA) bilan to'liq integratsiya\n"
        f"• {emo('folder')} Telegramdagi barcha Papkalarni (Folders) avtomatik o'qish va 1 bosishda tanlash\n"
        f"• {emo('tabs')} <b>Telegram Hikoyalarini (Stories)</b> kanallarga avtomatik tarqatish\n"
        f"• {emo('star')} Telegram Premium emojilarni va formatlarni 100% buzmasdan uzatish (Forward)\n"
        f"• {emo('timer')} Istalgan vaqt oralig'ini belgilash (1, 2, 3, 5, 10... minut)\n"
        f"• {emo('warning')} Telegram cheklovlariga qarshi xavfsiz pauzalar"
    )
    await call.message.edit_text(about_text, reply_markup=kb.login_method_kb())
    await call.answer()

# --- ADMIN PANEL ---

@dp.callback_query(F.data == "menu_admin_panel")
async def cb_admin_panel(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Siz admin emassiz!", show_alert=True)
        return
        
    active_broadcasters = db.get_active_broadcasters()
    text = (
        f"{emo('lock')} <b>Admin Panel</b>\n\n"
        f"{emo('user')} <b>Admin ID:</b> <code>{ADMIN_ID}</code>\n"
        f"{emo('rocket')} <b>Hozirda faol tarqatuvchilar:</b> <b>{len(active_broadcasters)}</b> ta\n"
        f"{emo('check')} Bot holati: <b>Ishchi rejimda</b>"
    )
    markup = kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text=" Asosiy menyu", callback_data="menu_back_main", icon_custom_emoji_id=PREMIUM_EMOJIS["back"], style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()

# --- AKKAUNT ULASH ---

@dp.callback_query(F.data == "menu_connect_account")
async def cb_connect_account(call: CallbackQuery):
    await call.message.edit_text(
        f"{emo('link')} <b>Akkauntni qaysi usulda ulamoqchisiz?</b>\n\n"
        f"1️⃣ <b>Telefon raqam orqali:</b> Raqamingizga tasdiqlash kodi yuboriladi.\n"
        f"2️⃣ <b>QR-kod orqali:</b> Telegram ilovangiz orqali QR-kodni skaner qilasiz.",
        reply_markup=kb.login_method_kb()
    )
    await call.answer()

@dp.callback_query(F.data == "login_method_phone")
async def cb_login_phone(call: CallbackQuery, state: FSMContext):
    await state.set_state(AuthStates.waiting_phone)
    await call.message.edit_text(
        f"{emo('phone')} <b>Telegram akkauntingiz telefon raqamini kiriting:</b>\n\n"
        "<i>Xalqaro formatda yuboring, masalan:</i> <code>+998901234567</code>",
        reply_markup=kb.cancel_action_kb()
    )
    await call.answer()

@dp.message(AuthStates.waiting_phone)
async def process_phone_input(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "")
    if not (phone.startswith("+") and len(phone) >= 10):
        await message.answer(
            f"{emo('warning')} Raqam formati noto'g'ri. Iltimos, xalqaro formatda kiriting:\nMasalan: <code>+998901234567</code>",
            reply_markup=kb.cancel_action_kb()
        )
        return
    
    wait_msg = await message.answer(f"{emo('loading')} Kod yuborilmoqda, kuting...")
    res = await ub.start_phone_login(message.from_user.id, phone)
    
    if res["status"] == "ok":
        await state.set_state(AuthStates.waiting_sms_code)
        await wait_msg.edit_text(
            f"{emo('mail')} <b>{phone}</b> raqamiga tasdiqlash kodi yuborildi!\n\n"
            "Iltimos, Telegram ilovangizga yoki SMS orqali kelgan kodni kiriting:\n\n"
            "<i>(Maslahat: Agar kod kelmasa, probel bilan yozing: masalan <code>1 2 3 4 5</code>)</i>",
            reply_markup=kb.cancel_action_kb()
        )
    elif res["status"] == "flood":
        await wait_msg.edit_text(
            f"{emo('cross')} Telegram cheklovi (FloodWait): Iltimos, <b>{res['seconds']}</b> soniyadan keyin qaytadan urinib ko'ring.",
            reply_markup=kb.cancel_action_kb()
        )
        await state.clear()
    else:
        await wait_msg.edit_text(
            f"{emo('cross')} Xatolik yuz berdi: {res.get('message')}\n\nQaytadan urinib ko'ring:",
            reply_markup=kb.cancel_action_kb()
        )

@dp.message(AuthStates.waiting_sms_code)
async def process_code_input(message: Message, state: FSMContext):
    code = message.text.strip()
    wait_msg = await message.answer(f"{emo('loading')} Kod tekshirilmoqda...")
    
    res = await ub.verify_phone_code(message.from_user.id, code)
    
    if res["status"] == "success":
        await state.clear()
        user_info = res["user"]
        await wait_msg.edit_text(
            f"{emo('star')} <b>Akkaunt muvaffaqiyatli ulandi!</b>\n\n"
            f"{emo('user')} Ism: <b>{user_info.first_name}</b>\n"
            f"🔹 Username: @{user_info.username or 'mavjud emas'}"
        )
        text, markup = await get_main_menu_text_and_kb(message.from_user.id)
        await message.answer(text, reply_markup=markup)
        
    elif res["status"] == "2fa_required":
        await state.set_state(AuthStates.waiting_2fa_password)
        await wait_msg.edit_text(
            f"{emo('lock')} <b>Ikki bosqichli autentifikatsiya (2FA)!</b>\n\n"
            "Akkauntingizda 2-bosqichli parol o'rnatilgan.\n"
            "Iltimos, parolingizni kiriting:",
            reply_markup=kb.cancel_action_kb()
        )
    elif res["status"] == "invalid_code":
        await wait_msg.edit_text(
            f"{emo('cross')} <b>Tasdiqlash kodi noto'g'ri!</b>\n\nIltimos, qaytadan diqqat bilan kiriting:",
            reply_markup=kb.cancel_action_kb()
        )
    else:
        await wait_msg.edit_text(
            f"{emo('cross')} Xatolik: {res.get('message')}\nQaytadan urinib ko'ring:",
            reply_markup=kb.cancel_action_kb()
        )

@dp.message(AuthStates.waiting_2fa_password)
async def process_2fa_password(message: Message, state: FSMContext):
    password = message.text.strip()
    wait_msg = await message.answer(f"{emo('loading')} Parol tekshirilmoqda...")
    
    res = await ub.verify_2fa_password(message.from_user.id, password)
    
    if res["status"] == "success":
        await state.clear()
        user_info = res["user"]
        await wait_msg.edit_text(
            f"{emo('check')} <b>2FA tasdiqlandi va akkaunt muvaffaqiyatli ulandi!</b>\n\n"
            f"{emo('user')} Ism: <b>{user_info.first_name}</b>\n"
            f"🔹 Username: @{user_info.username or 'mavjud emas'}"
        )
        text, markup = await get_main_menu_text_and_kb(message.from_user.id)
        await message.answer(text, reply_markup=markup)
    elif res["status"] == "invalid_password":
        await wait_msg.edit_text(
            f"{emo('cross')} <b>2-bosqichli parol noto'g'ri!</b>\n\nIltimos, to'g'ri parolni kiriting:",
            reply_markup=kb.cancel_action_kb()
        )
    else:
        await wait_msg.edit_text(
            f"{emo('cross')} Xatolik: {res.get('message')}",
            reply_markup=kb.cancel_action_kb()
        )

@dp.callback_query(F.data == "login_method_qr")
async def cb_login_qr(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    wait_msg = await call.message.edit_text(f"{emo('loading')} QR kod yaratilmoqda, kuting...")
    
    async def on_success(user):
        try:
            await bot.send_message(
                user_id,
                f"{emo('star')} <b>QR-kod orqali akkaunt muvaffaqiyatli ulandi!</b>\n\n"
                f"{emo('user')} Ism: <b>{user.first_name}</b>\n"
                f"🔹 Username: @{user.username or 'mavjud emas'}"
            )
            text, markup = await get_main_menu_text_and_kb(user_id)
            await bot.send_message(user_id, text, reply_markup=markup)
        except Exception as e:
            logger.error(f"on_success error: {e}")
            
    async def on_2fa():
        try:
            await state.set_state(AuthStates.waiting_2fa_password)
            await bot.send_message(
                user_id,
                f"{emo('lock')} <b>QR-kod skaner qilindi, lekin akkauntingizda 2FA parol mavjud!</b>\n\n"
                "Iltimos, 2-bosqichli parolingizni yozib yuboring:",
                reply_markup=kb.cancel_action_kb()
            )
        except Exception as e:
            logger.error(f"on_2fa error: {e}")
            
    async def on_expire():
        try:
            await bot.send_message(
                user_id,
                f"{emo('hourglass')} QR-kodning amal qilish muddati tugadi (2 daqiqa).\nQaytadan urinib ko'ring:",
                reply_markup=kb.login_method_kb()
            )
        except Exception as e:
            logger.error(f"on_expire error: {e}")

    res = await ub.start_qr_login(user_id, on_success, on_2fa, on_expire)
    if res["status"] == "ok":
        photo_file = BufferedInputFile(res["image_bytes"], filename="qr.png")
        await call.message.delete()
        await bot.send_photo(
            chat_id=user_id,
            photo=photo_file,
            caption=(
                f"{emo('camera')} <b>Telegram ilovangiz orqali QR-kodni skanerlang:</b>\n\n"
                "1. Telegram sozlamalariga kiring (Settings)\n"
                "2. <b>Qurilmalar (Devices)</b> bo'limini oching\n"
                "3. <b>QR kodni skanerlash (Link Desktop Device)</b> tugmasini bosing va ushbu kodga qarating.\n\n"
                f"{emo('loading')} <i>Kutilmoqda... (Amal qilish muddati: 2 daqiqa)</i>"
            ),
            reply_markup=kb.cancel_action_kb()
        )
    else:
        await wait_msg.edit_text(f"{emo('cross')} Xatolik yuz berdi: {res.get('message')}", reply_markup=kb.cancel_action_kb())
    await call.answer()

# --- PAPKALAR VA KANALLAR RO'YXATI ---

async def ensure_channels_cache(user_id: int, user: dict):
    if user_id not in channels_cache:
        folders, all_channels = await ub.get_user_folders_and_dialogs(user["session_string"])
        saved_selected = {ch["id"] for ch in user.get("selected_channels", [])}
        channels_cache[user_id] = {
            "folders": folders or [],
            "channels": all_channels or [],
            "channels_dict": {ch["id"]: ch for ch in (all_channels or [])},
            "selected_ids": saved_selected
        }
    return channels_cache[user_id]

@dp.callback_query(F.data == "menu_folders")
async def cb_show_folders(call: CallbackQuery):
    user_id = call.from_user.id
    user = db.get_user(user_id)
    if not user or not user.get("session_string"):
        await call.answer("Avval akkauntingizni ulang!", show_alert=True)
        return
        
    if user_id not in channels_cache:
        await call.message.edit_text(f"{emo('loading')} Telegramdagi papkalar va kanallaringiz yuklanmoqda...")
    
    cache = await ensure_channels_cache(user_id, user)
    folders = cache["folders"]
    all_channels = cache["channels"]
    selected_ids = cache["selected_ids"]
    
    markup = kb.folders_menu_kb(folders, all_channels, selected_ids)
    await call.message.edit_text(
        f"{emo('folder')} <b>Telegram Papkalari va Kanallarni tanlash:</b>\n\n"
        f"{emo('speaker')} Jami topilgan kanallar/guruhlar: <b>{len(all_channels)}</b> ta\n"
        f"{emo('check')} Hozirda tanlangan: <b>{len(selected_ids)}</b> ta\n\n"
        f"{emo('bulb')} <i>Istalgan papkani bosing — uning ichidagi barcha guruh va kanallar bir zumda belgilanadi!</i>",
        reply_markup=markup
    )
    await call.answer()

@dp.callback_query(F.data.startswith("toggle_folder_"))
async def cb_toggle_folder(call: CallbackQuery):
    folder_id = int(call.data.split("_")[-1])
    user_id = call.from_user.id
    user = db.get_user(user_id)
    cache = await ensure_channels_cache(user_id, user)
    
    target_folder = next((f for f in cache["folders"] if f["id"] == folder_id), None)
    if not target_folder:
        await call.answer("Papka topilmadi!", show_alert=True)
        return
        
    f_ids = set(target_folder["channel_ids"])
    selected_ids = cache["selected_ids"]
    
    if f_ids.issubset(selected_ids) and f_ids:
        selected_ids.difference_update(f_ids)
        await call.answer(f"❌ 📁 {target_folder['title']} papkasi tanlovdan olib tashlandi!")
    else:
        selected_ids.update(f_ids)
        await call.answer(f"✅ 📁 {target_folder['title']} papkasidagi barcha ({len(f_ids)} ta) kanal tanlandi!")
        
    markup = kb.folders_menu_kb(cache["folders"], cache["channels"], selected_ids)
    await call.message.edit_text(
        f"{emo('folder')} <b>Telegram Papkalari va Kanallarni tanlash:</b>\n\n"
        f"{emo('speaker')} Jami topilgan kanallar/guruhlar: <b>{len(cache['channels'])}</b> ta\n"
        f"{emo('check')} Hozirda tanlangan: <b>{len(selected_ids)}</b> ta\n\n"
        f"{emo('bulb')} <i>Istalgan papkani bosing — uning ichidagi barcha guruh va kanallar bir zumda belgilanadi!</i>",
        reply_markup=markup
    )

@dp.callback_query(F.data == "select_all_global")
async def cb_select_all_global(call: CallbackQuery):
    user_id = call.from_user.id
    user = db.get_user(user_id)
    cache = await ensure_channels_cache(user_id, user)
    for ch in cache["channels"]:
        cache["selected_ids"].add(ch["id"])
    
    markup = kb.folders_menu_kb(cache["folders"], cache["channels"], cache["selected_ids"])
    await call.message.edit_reply_markup(reply_markup=markup)
    await call.answer(f"Barcha {len(cache['channels'])} ta kanal va guruh tanlandi!")

@dp.callback_query(F.data == "deselect_all_global")
async def cb_deselect_all_global(call: CallbackQuery):
    user_id = call.from_user.id
    user = db.get_user(user_id)
    cache = await ensure_channels_cache(user_id, user)
    cache["selected_ids"].clear()
    
    markup = kb.folders_menu_kb(cache["folders"], cache["channels"], cache["selected_ids"])
    await call.message.edit_reply_markup(reply_markup=markup)
    await call.answer("Barcha tanlovlar olib tashlandi!")

@dp.callback_query(F.data.startswith("menu_channels_"))
async def cb_show_channels(call: CallbackQuery):
    user_id = call.from_user.id
    user = db.get_user(user_id)
    if not user or not user.get("session_string"):
        await call.answer("Avval akkauntingizni ulang!", show_alert=True)
        return
    
    page = int(call.data.split("_")[-1])
    cache = await ensure_channels_cache(user_id, user)
    all_channels = cache["channels"]
    selected_ids = cache["selected_ids"]
    
    if not all_channels:
        await call.message.edit_text(
            f"{emo('warning')} Akkauntingiz hech qanday kanal yoki guruhga a'zo emas!",
            reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
                [kb.InlineKeyboardButton(text=" Ortga", callback_data="menu_folders", icon_custom_emoji_id=PREMIUM_EMOJIS["back"], style="danger")]
            ])
        )
        return
        
    markup = kb.channels_paginated_kb(all_channels, selected_ids, page=page)
    await call.message.edit_text(
        f"{emo('clipboard')} <b>Barcha kanallar ro'yxati:</b>\n"
        f"Jami: <b>{len(all_channels)}</b> ta\n"
        f"Tanlangan: <b>{len(selected_ids)}</b> ta\n\n"
        "<i>Har bir kanalni alohida belgilashingiz mumkin:</i>",
        reply_markup=markup
    )
    await call.answer()

@dp.callback_query(F.data.startswith("toggle_ch_"))
async def cb_toggle_channel(call: CallbackQuery):
    parts = call.data.split("_")
    ch_id = int(parts[2])
    page = int(parts[3])
    user_id = call.from_user.id
    user = db.get_user(user_id)
    cache = await ensure_channels_cache(user_id, user)
    
    selected_ids = cache["selected_ids"]
    if ch_id in selected_ids:
        selected_ids.remove(ch_id)
    else:
        selected_ids.add(ch_id)
        
    markup = kb.channels_paginated_kb(cache["channels"], selected_ids, page=page)
    try:
        await call.message.edit_reply_markup(reply_markup=markup)
    except Exception:
        pass
    await call.answer()

@dp.callback_query(F.data == "save_channels_confirm")
async def cb_save_channels_confirm(call: CallbackQuery):
    user_id = call.from_user.id
    user = db.get_user(user_id)
    cache = await ensure_channels_cache(user_id, user)
    
    selected_ids = cache["selected_ids"]
    ch_dict = cache["channels_dict"]
    
    final_list = [ch_dict[cid] for cid in selected_ids if cid in ch_dict]
    db.update_user_fields(user_id, selected_channels=final_list)
    channels_cache.pop(user_id, None)
    
    await call.answer(f"✅ {len(final_list)} ta kanal/guruh saqlandi!", show_alert=True)
    text, markup = await get_main_menu_text_and_kb(user_id)
    await call.message.edit_text(text, reply_markup=markup)

# --- VAQT ORALIG'I (INTERVAL) ---

@dp.callback_query(F.data == "menu_interval")
async def cb_menu_interval(call: CallbackQuery):
    user = db.get_user(call.from_user.id)
    curr = user.get("interval_minutes", 2) if user else 2
    await call.message.edit_text(
        f"{emo('timer')} <b>Tarqatish har necha daqiqada yuborilsin?</b>\n\n"
        f"Hozirgi vaqt: <b>{curr} minut</b>\n"
        "<i>Kerakli vaqtni tanlang:</i>",
        reply_markup=kb.interval_kb()
    )
    await call.answer()

@dp.callback_query(F.data.startswith("set_interval_"))
async def cb_set_interval(call: CallbackQuery):
    mins = int(call.data.split("_")[-1])
    db.update_user_fields(call.from_user.id, interval_minutes=mins)
    await call.answer(f"✅ Interval {mins} minut qilib belgilandi!", show_alert=True)
    text, markup = await get_main_menu_text_and_kb(call.from_user.id)
    await call.message.edit_text(text, reply_markup=markup)

# --- REKLAMA POSTI KIRITISH ---

@dp.callback_query(F.data == "menu_set_message")
async def cb_menu_set_message(call: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastStates.waiting_post_message)
    await call.message.edit_text(
        f"{emo('write')} <b>Reklama xabaringizni yuboring:</b>\n\n"
        "Siz istalgan xabarni yuborishingiz mumkin:\n"
        f"• {emo('star')} <b>Telegram Premium emojilar</b> bilan bezatilgan matn\n"
        f"• {emo('image')} Rasmli yoki videoli post (tagidagi izohi bilan)\n"
        f"• {emo('link')} Havolalar va chiroyli formatlangan matnlar\n\n"
        "<i>Xabaringizni to'g'ridan-to'g'ri shu yerga yozib yoki boshqa kanaldan forward qilib yuboring:</i>",
        reply_markup=kb.cancel_action_kb()
    )
    await call.answer()

@dp.message(BroadcastStates.waiting_post_message)
async def process_post_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user or not user.get("session_string"):
        await message.answer("Avval akkauntingizni ulang!", reply_markup=kb.main_menu_kb(False))
        await state.clear()
        return
        
    wait_msg = await message.answer(f"{emo('save')} Reklama posti saqlanmoqda...")
    bot_info = await bot.get_me()
    
    saved_info = await ub.save_user_post_to_saved(user["session_string"], bot_info.username)
    
    if saved_info:
        db.update_user_fields(
            user_id,
            broadcast_type="post",
            broadcast_forward_chat_id=saved_info["forward_chat_id"],
            broadcast_forward_msg_id=saved_info["forward_msg_id"],
            broadcast_msg_text=saved_info["text"],
            broadcast_story_url=None
        )
        await wait_msg.edit_text(f"{emo('check')} <b>Reklama posti barcha format va Premium emojilari bilan saqlandi!</b>")
    else:
        text_content = message.text or message.caption or ""
        db.update_user_fields(
            user_id, 
            broadcast_type="post",
            broadcast_msg_text=text_content, 
            broadcast_forward_msg_id=None,
            broadcast_story_url=None
        )
        await wait_msg.edit_text(f"{emo('check')} <b>Reklama matni saqlandi!</b>")
        
    await state.clear()
    main_text, markup = await get_main_menu_text_and_kb(user_id)
    await message.answer(main_text, reply_markup=markup)

# --- TELEGRAM HIKOYA (STORY) KIRITISH ---

@dp.callback_query(F.data == "menu_set_story")
async def cb_menu_set_story(call: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastStates.waiting_story_message)
    await call.message.edit_text(
        f"{emo('tabs')} <b>Telegram Hikoyangizni (Story) yuboring:</b>\n\n"
        "Siz 2 xil usulda yuborishingiz mumkin:\n\n"
        "1️⃣ <b>Havola (Link) orqali:</b>\n"
        "Hikoyangiz havolasini yuboring:\n"
        "<i>Masalan:</i> <code>https://t.me/username/s/12</code>\n\n"
        "2️⃣ <b>To'g'ridan-to'g'ri ulashish (Share):</b>\n"
        "Telegramda o'zingizning yoki kanalingizning Hikoyasini (Story) oching -> <b>Ulashish (Share)</b> tugmasini bosing -> Ushbu botga yuboring!\n\n"
        "<i>Bot ushbu hikoyani siz tanlagan barcha kanallarga avtomatik tarqatadi.</i>",
        reply_markup=kb.cancel_action_kb()
    )
    await call.answer()

@dp.message(BroadcastStates.waiting_story_message)
async def process_story_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user or not user.get("session_string"):
        await message.answer("Avval akkauntingizni ulang!", reply_markup=kb.main_menu_kb(False))
        await state.clear()
        return
        
    wait_msg = await message.answer(f"{emo('loading')} Hikoya tekshirilmoqda va saqlanmoqda...")
    bot_info = await bot.get_me()
    
    story_raw = ""
    if message.story:
        s_chat = message.story.chat
        s_id = message.story.id
        if s_chat and s_chat.username:
            story_raw = f"https://t.me/{s_chat.username}/s/{s_id}"
        elif s_chat:
            cid = str(s_chat.id).replace("-100", "")
            story_raw = f"https://t.me/c/{cid}/s/{s_id}"
    elif message.text:
        story_raw = message.text.strip()
    elif message.caption:
        story_raw = message.caption.strip()
        
    saved_info = await ub.save_user_story_post(user["session_string"], bot_info.username, story_raw)
    
    if saved_info:
        db.update_user_fields(
            user_id,
            broadcast_type="story",
            broadcast_forward_chat_id=saved_info.get("forward_chat_id"),
            broadcast_forward_msg_id=saved_info.get("forward_msg_id"),
            broadcast_msg_text=saved_info.get("text"),
            broadcast_story_url=saved_info.get("story_url")
        )
        await wait_msg.edit_text(
            f"{emo('check')} <b>Telegram Hikoyasi (Story) saqlandi!</b>\n\n"
            f"Endi <b>'Boshlash'</b> tugmasini bossangiz, belgilangan kanallarga ushbu hikoya tarqatiladi."
        )
    else:
        await wait_msg.edit_text(
            f"{emo('warning')} <b>Hikoyani aniqlab bo'lmadi!</b>\n\n"
            "Iltimos, hikoyangiz havolasini yuboring (masalan: <code>https://t.me/username/s/1</code>) "
            "yoki hikoyani ochib, 'Ulashish (Share)' tugmasi orqali botga jo'nating.",
            reply_markup=kb.cancel_action_kb()
        )
        return
        
    await state.clear()
    main_text, markup = await get_main_menu_text_and_kb(user_id)
    await message.answer(main_text, reply_markup=markup)

# To'g'ridan-to'g'ri (tugmani bosmasdan ham) Hikoya ulashilganda yoki havola yuborilganda avtomatik qabul qilish
@dp.message(F.story)
async def auto_handle_shared_story(message: Message, state: FSMContext):
    curr_state = await state.get_state()
    if curr_state in [AuthStates.waiting_phone, AuthStates.waiting_sms_code, AuthStates.waiting_2fa_password]:
        return
    await process_story_message(message, state)

@dp.message(F.text.regexp(r'(?:https?://)?(?:t(?:elegram)?\.me)/(?:c/\d+|[a-zA-Z0-9_]+)/s/\d+'))
async def auto_handle_story_link(message: Message, state: FSMContext):
    curr_state = await state.get_state()
    if curr_state in [AuthStates.waiting_phone, AuthStates.waiting_sms_code, AuthStates.waiting_2fa_password]:
        return
    await process_story_message(message, state)

# --- REKLAMANI BOSHLASH VA TO'XTATISH ---

@dp.callback_query(F.data == "broadcast_start")
async def cb_broadcast_start(call: CallbackQuery):
    user_id = call.from_user.id
    user = db.get_user(user_id)
    
    if not user or not user.get("session_string"):
        await call.answer("Akkaunt ulanmagan!", show_alert=True)
        return
        
    selected = user.get("selected_channels", [])
    if not selected:
        await call.answer("⚠️ Avval kanallarni tanlang!", show_alert=True)
        return
        
    has_post = user.get("broadcast_forward_msg_id") or user.get("broadcast_msg_text") or user.get("broadcast_story_url")
    if not has_post:
        await call.answer("⚠️ Avval reklama posti yoki hikoyani kiriting!", show_alert=True)
        return
        
    ub.start_user_broadcast(user_id, bot)
    await call.answer("🚀 Tarqatish boshlandi!", show_alert=True)
    text, markup = await get_main_menu_text_and_kb(user_id)
    await call.message.edit_text(text, reply_markup=markup)

@dp.callback_query(F.data == "broadcast_stop")
async def cb_broadcast_stop(call: CallbackQuery):
    user_id = call.from_user.id
    ub.stop_user_broadcast(user_id)
    await call.answer("⏸ Tarqatish to'xtatildi!", show_alert=True)
    text, markup = await get_main_menu_text_and_kb(user_id)
    await call.message.edit_text(text, reply_markup=markup)

# --- STATISTIKA VA AKKAUNT ---

@dp.callback_query(F.data == "menu_status")
async def cb_menu_status(call: CallbackQuery):
    user = db.get_user(call.from_user.id)
    if not user:
        return
        
    is_active = user.get("is_broadcasting")
    status_str = f"{emo('dot_green')} Faol (Tarqatilmoqda)" if is_active else f"{emo('cross')} To'xtatilgan"
    b_type = "📖 Telegram Hikoyasi (Story)" if user.get("broadcast_type") == "story" else "✍️ Post (Xabar)"
    last_sent = user.get("last_sent_time")
    if last_sent and last_sent > 0:
        last_str = datetime.datetime.fromtimestamp(last_sent).strftime("%Y-%m-%d %H:%M:%S")
    else:
        last_str = "Hali yuborilmagan"
        
    stat_text = (
        f"{emo('stats')} <b>Tarqatish holati va statistikasi:</b>\n\n"
        f"{emo('rocket')} <b>Holat:</b> {status_str}\n"
        f"{emo('tabs')} <b>Turi:</b> {b_type}\n"
        f"{emo('timer')} <b>Interval:</b> har {user.get('interval_minutes', 2)} minutda\n"
        f"{emo('speaker')} <b>Tanlangan kanallar soni:</b> {len(user.get('selected_channels', []))} ta\n"
        f"{emo('mail')} <b>Jami yuborilganlar:</b> {user.get('total_sent_count', 0)} ta\n"
        f"{emo('loading')} <b>Oxirgi yuborilgan vaqt:</b> <code>{last_str}</code>"
    )
    await call.message.edit_text(stat_text, reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text=" Asosiy menyu", callback_data="menu_back_main", icon_custom_emoji_id=PREMIUM_EMOJIS["back"], style="danger")]
    ]))
    await call.answer()

@dp.callback_query(F.data == "menu_account")
async def cb_menu_account(call: CallbackQuery):
    user = db.get_user(call.from_user.id)
    phone = user.get("phone") or "Mavjud emas"
    name = user.get("first_name") or "Foydalanuvchi"
    username = f"@{user['username']}" if user.get("username") else "mavjud emas"
    
    text = (
        f"{emo('user')} <b>Ulangan akkaunt ma'lumotlari:</b>\n\n"
        f"🔹 Ism: <b>{name}</b>\n"
        f"🔹 Username: {username}\n"
        f"{emo('phone')} Telefon: <code>{phone}</code>\n\n"
        "<i>Akkauntni tizimdan uzish uchun quyidagi tugmani bosing:</i>"
    )
    await call.message.edit_text(text, reply_markup=kb.account_settings_kb())
    await call.answer()

@dp.callback_query(F.data == "account_logout")
async def cb_account_logout(call: CallbackQuery):
    user_id = call.from_user.id
    ub.stop_user_broadcast(user_id)
    db.delete_user_session(user_id)
    channels_cache.pop(user_id, None)
    await call.answer("🚪 Akkaunt tizimdan uzildi!", show_alert=True)
    text, markup = await get_main_menu_text_and_kb(user_id)
    await call.message.edit_text(text, reply_markup=markup)

@dp.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()

# --- ISHGA TUSHIRISH (HOSTING VA CRASH RECOVERY BILAN) ---

async def start_render_web_server():
    """Render Free Tier Web Service uchun HTTP Health Check server"""
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    
    async def handle_root(request):
        return web.Response(text="Bot is running successfully on Render! 🚀", status=200)

    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_root)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 [RENDER] Web server {port}-portda ishga tushdi.")
    return runner

async def start_bot_service():
    print("🚀 [HOSTING] Bot xizmati ishga tushmoqda...")
    
    try:
        active_users = db.get_active_broadcasters()
        for uid in active_users:
            ub.start_user_broadcast(uid, bot)
            print(f"🔄 User {uid} uchun avto-tarqatish tiklandi.")
    except Exception as e:
        print(f"⚠️ Tiklashda ogohlantirish: {e}")
        
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

async def main():
    try:
        await start_render_web_server()
    except Exception as e:
        print(f"⚠️ Web serverni ishga tushirishda ogohlantirish: {e}")

    while True:
        try:
            await start_bot_service()
        except (KeyboardInterrupt, SystemExit):
            print("🛑 Bot to'xtatildi.")
            break
        except Exception as e:
            logger.error(f"❌ [HOSTING CRASH RECOVERY] Xatolik: {e}. 5 soniyadan so'ng qayta ulanmoqda...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
