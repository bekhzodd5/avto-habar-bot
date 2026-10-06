import asyncio
import io
import re
import json
import logging
from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.tl import functions, types
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PasswordHashInvalidError,
    FloodWaitError,
    AuthKeyUnregisteredError,
    UserDeactivatedError
)
import qrcode

from config import API_ID, API_HASH
import database as db

logger = logging.getLogger(__name__)

active_clients = {}  # user_id: TelegramClient
login_states = {}    # user_id: dict
broadcast_tasks = {} # user_id: asyncio.Task

def get_client_for_session(session_string: str) -> TelegramClient:
    return TelegramClient(StringSession(session_string), API_ID, API_HASH)

async def start_phone_login(user_id: int, phone: str):
    """Telefon raqamga SMS/Telegram orqali kod jo'natish"""
    await cancel_login(user_id)
    
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    
    try:
        sent_code = await client.send_code_request(phone)
        login_states[user_id] = {
            "type": "phone",
            "client": client,
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash
        }
        return {"status": "ok"}
    except FloodWaitError as e:
        await client.disconnect()
        return {"status": "flood", "seconds": e.seconds}
    except Exception as e:
        await client.disconnect()
        return {"status": "error", "message": str(e)}

async def verify_phone_code(user_id: int, code: str):
    """Kiritilgan kodni tekshirish"""
    data = login_states.get(user_id)
    if not data or data.get("type") != "phone":
        return {"status": "no_login"}
    
    client = data["client"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]
    
    clean_code = "".join(filter(str.isdigit, code))
    
    try:
        await client.sign_in(phone=phone, code=clean_code, phone_code_hash=phone_code_hash)
        me = await client.get_me()
        session_str = client.session.save()
        db.save_user_session(
            user_id=user_id,
            session_string=session_str,
            phone=phone,
            first_name=me.first_name,
            username=me.username
        )
        login_states.pop(user_id, None)
        await client.disconnect()
        return {"status": "success", "user": me}
    except SessionPasswordNeededError:
        login_states[user_id]["type"] = "2fa"
        return {"status": "2fa_required"}
    except PhoneCodeInvalidError:
        return {"status": "invalid_code"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def verify_2fa_password(user_id: int, password: str):
    """2FA parolni tekshirish"""
    data = login_states.get(user_id)
    if not data or data.get("type") != "2fa":
        return {"status": "no_login"}
    
    client = data["client"]
    try:
        await client.sign_in(password=password)
        me = await client.get_me()
        session_str = client.session.save()
        db.save_user_session(
            user_id=user_id,
            session_string=session_str,
            phone=data.get("phone", getattr(me, "phone", "")),
            first_name=me.first_name,
            username=me.username
        )
        login_states.pop(user_id, None)
        await client.disconnect()
        return {"status": "success", "user": me}
    except PasswordHashInvalidError:
        return {"status": "invalid_password"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def start_qr_login(user_id: int, on_success_callback, on_2fa_callback, on_expire_callback):
    """QR-kod orqali autentifikatsiya"""
    await cancel_login(user_id)
    
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    
    try:
        qr = await client.qr_login()
        
        qr_img = qrcode.QRCode(box_size=8, border=2)
        qr_img.add_data(qr.url)
        qr_img.make(fit=True)
        img = qr_img.make_image(fill_color="black", back_color="white")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        
        async def wait_qr():
            try:
                user = await qr.wait(timeout=120)
                session_str = client.session.save()
                db.save_user_session(
                    user_id=user_id,
                    session_string=session_str,
                    phone=getattr(user, "phone", ""),
                    first_name=user.first_name,
                    username=user.username
                )
                login_states.pop(user_id, None)
                await client.disconnect()
                await on_success_callback(user)
            except SessionPasswordNeededError:
                login_states[user_id] = {
                    "type": "2fa",
                    "client": client
                }
                await on_2fa_callback()
            except asyncio.TimeoutError:
                await client.disconnect()
                login_states.pop(user_id, None)
                await on_expire_callback()
            except Exception as e:
                await client.disconnect()
                login_states.pop(user_id, None)
                logger.error(f"QR login xatosi: {e}")
        
        task = asyncio.create_task(wait_qr())
        login_states[user_id] = {
            "type": "qr",
            "client": client,
            "qr": qr,
            "qr_task": task
        }
        return {"status": "ok", "image_bytes": buf.getvalue()}
    except Exception as e:
        await client.disconnect()
        return {"status": "error", "message": str(e)}

async def cancel_login(user_id: int):
    """Jarayondagi loginni bekor qilish"""
    data = login_states.pop(user_id, None)
    if data:
        if "qr_task" in data and not data["qr_task"].done():
            data["qr_task"].cancel()
        client = data.get("client")
        if client and client.is_connected():
            try:
                await client.disconnect()
            except Exception:
                pass

async def get_user_folders_and_dialogs(session_string: str):
    """
    Foydalanuvchining Telegramdagi papkalari (Folders) va barcha kanal/guruhlarini olish
    """
    client = get_client_for_session(session_string)
    await client.connect()
    
    if not await client.is_user_authorized():
        await client.disconnect()
        return None, None
    
    try:
        dialogs = await client.get_dialogs()
        filters_resp = await client(functions.messages.GetDialogFiltersRequest())
        
        channels_dict = {}
        for d in dialogs:
            if d.is_channel or d.is_group:
                channels_dict[d.id] = {
                    "id": d.id,
                    "title": d.name or "Nomsiz",
                    "type": "Kanal" if (d.is_channel and not d.is_group) else "Guruh",
                    "username": getattr(d.entity, "username", None)
                }
        
        folders_list = []
        for f in filters_resp.filters:
            if isinstance(f, (types.DialogFilter, types.DialogFilterChatlist)):
                title = f.title.text if hasattr(f.title, "text") else str(f.title)
                peer_ids = set()
                for p in (getattr(f, "pinned_peers", []) + getattr(f, "include_peers", [])):
                    peer_ids.add(utils.get_peer_id(p))
                
                ch_ids = []
                for did, ch in channels_dict.items():
                    if did in peer_ids:
                        ch_ids.append(did)
                    elif getattr(f, "broadcasts", False) and ch["type"] == "Kanal":
                        ch_ids.append(did)
                    elif getattr(f, "groups", False) and ch["type"] == "Guruh":
                        ch_ids.append(did)
                
                exclude_ids = {utils.get_peer_id(p) for p in getattr(f, "exclude_peers", [])}
                final_ids = [cid for cid in ch_ids if cid not in exclude_ids]
                
                folders_list.append({
                    "id": f.id,
                    "title": title,
                    "channel_ids": final_ids,
                    "count": len(final_ids)
                })
                
        return folders_list, list(channels_dict.values())
    finally:
        await client.disconnect()

async def save_user_post_to_saved(session_string: str, bot_username: str):
    """Foydalanuvchi botga yuborgan oxirgi postni o'zining Saved Messages'iga saqlash"""
    client = get_client_for_session(session_string)
    await client.connect()
    
    if not await client.is_user_authorized():
        await client.disconnect()
        return None
        
    try:
        bot_peer = await client.get_input_entity(bot_username)
        messages = await client.get_messages(bot_peer, limit=5)
        target_msg = None
        for m in messages:
            if m.out:
                target_msg = m
                break
        if not target_msg and messages:
            target_msg = messages[0]
            
        if target_msg:
            fwd = await client.forward_messages('me', target_msg)
            text_preview = target_msg.text or (target_msg.message or "Media post")
            return {
                "forward_chat_id": "me",
                "forward_msg_id": fwd.id,
                "text": text_preview[:200],
                "type": "post"
            }
    except Exception as e:
        logger.error(f"Xabarni saqlashda xatolik: {e}")
    finally:
        await client.disconnect()
    return None

async def save_user_story_post(session_string: str, bot_username: str, text_or_url: str = None):
    """Foydalanuvchi yuborgan Telegram Hikoyasini (Story) saqlash"""
    client = get_client_for_session(session_string)
    await client.connect()
    
    if not await client.is_user_authorized():
        await client.disconnect()
        return None
        
    try:
        # 1. Agar foydalanuvchi Story havolasini yuborgan bo'lsa (https://t.me/username/s/12)
        if text_or_url and "t.me/" in text_or_url:
            match = re.search(r'(?:https?://)?(?:t(?:elegram)?\.me)/(?:c/(\d+)|([a-zA-Z0-9_]+))/s/(\d+)', text_or_url.strip())
            if match:
                c_id, username, s_id = match.groups()
                story_id = int(s_id)
                peer_target = int(f"-100{c_id}") if c_id else username
                peer_input = await client.get_input_entity(peer_target)
                
                msg_id = None
                try:
                    # O'zining Saved Messages'iga yuborib ko'ramiz
                    story_file = types.InputMediaStory(peer=peer_input, id=story_id)
                    sent = await client.send_message('me', file=story_file)
                    msg_id = sent.id
                except Exception as ex:
                    logger.warning(f"Saved Messages'ga hikoya yuborishda eslatma: {ex}")
                
                return {
                    "forward_chat_id": "me" if msg_id else None,
                    "forward_msg_id": msg_id,
                    "text": f"📖 Hikoya: {text_or_url.strip()}",
                    "story_url": text_or_url.strip(),
                    "type": "story"
                }

        # 2. Agar foydalanuvchi Telegramdan botga Hikoyani ulashgan (Share) bo'lsa
        bot_peer = await client.get_input_entity(bot_username)
        messages = await client.get_messages(bot_peer, limit=5)
        target_msg = None
        for m in messages:
            if m.out:
                target_msg = m
                break
        if not target_msg and messages:
            target_msg = messages[0]
            
        if target_msg:
            extracted_url = text_or_url
            if hasattr(target_msg, 'media') and isinstance(target_msg.media, types.MessageMediaStory):
                try:
                    p = target_msg.media.peer
                    s_id = target_msg.media.id
                    p_entity = await client.get_entity(p)
                    if hasattr(p_entity, 'username') and p_entity.username:
                        extracted_url = f"https://t.me/{p_entity.username}/s/{s_id}"
                except Exception:
                    pass

            # Agar bu Story bo'lsa yoki boshqa xabar bo'lsa ham 'me' ga forward qilamiz
            fwd = await client.forward_messages('me', target_msg)
            return {
                "forward_chat_id": "me",
                "forward_msg_id": fwd.id,
                "text": "📖 Telegram Hikoyasi (Story)",
                "story_url": extracted_url if extracted_url else None,
                "type": "story"
            }
    except Exception as e:
        logger.error(f"Hikoyani saqlashda xatolik: {e}")
    finally:
        await client.disconnect()
    return None

async def broadcast_worker(user_id: int, bot_instance):
    """Har X daqiqada post yoki hikoyani tarqatuvchi fon tsikli"""
    logger.info(f"Broadcast ishga tushdi user_id={user_id}")
    
    while True:
        try:
            user = db.get_user(user_id)
            if not user or not user["is_broadcasting"] or not user["session_string"]:
                break
            
            selected_channels = user["selected_channels"]
            if not selected_channels:
                db.update_user_fields(user_id, is_broadcasting=0)
                try:
                    await bot_instance.send_message(user_id, "⚠️ Hech qanday kanal tanlanmagan! Reklama tarqatish to'xtatildi.")
                except Exception:
                    pass
                break
            
            b_type = user.get("broadcast_type", "post")
            story_url = user.get("broadcast_story_url")
            fwd_msg_id = user["broadcast_forward_msg_id"]
            msg_text = user["broadcast_msg_text"]
            
            if not fwd_msg_id and not msg_text and not story_url:
                db.update_user_fields(user_id, is_broadcasting=0)
                try:
                    await bot_instance.send_message(user_id, "⚠️ Reklama xabari yoki hikoya kiritilmagan! Tarqatish to'xtatildi.")
                except Exception:
                    pass
                break
            
            client = get_client_for_session(user["session_string"])
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                db.update_user_fields(user_id, is_broadcasting=0, session_string=None)
                try:
                    await bot_instance.send_message(user_id, "❌ Akkaunt sessiyasi eskirgan yoki tizimdan chiqilgan. Iltimos, qaytadan kiring.")
                except Exception:
                    pass
                break
            
            # Agar story_url bo'lsa, input_story ni oldindan tayyorlaymiz
            prepared_story_file = None
            if b_type == "story" and story_url:
                match = re.search(r'(?:https?://)?(?:t(?:elegram)?\.me)/(?:c/(\d+)|([a-zA-Z0-9_]+))/s/(\d+)', story_url.strip())
                if match:
                    try:
                        c_id, uname, s_id = match.groups()
                        peer_target = int(f"-100{c_id}") if c_id else uname
                        input_p = await client.get_input_entity(peer_target)
                        prepared_story_file = types.InputMediaStory(peer=input_p, id=int(s_id))
                    except Exception as ex:
                        logger.warning(f"Story tayyorlashda xatolik: {ex}")
            
            success_count = 0
            fail_count = 0
            
            for ch in selected_channels:
                current_state = db.get_user(user_id)
                if not current_state or not current_state["is_broadcasting"]:
                    break
                
                ch_id = ch["id"]
                try:
                    sent_ok = False
                    # 1. Agar to'g'ridan-to'g'ri Story yuborish bo'lsa
                    if prepared_story_file:
                        try:
                            await client.send_message(ch_id, file=prepared_story_file)
                            sent_ok = True
                        except Exception as ex_story:
                            logger.warning(f"InputMediaStory yuborishda xatolik ({ch_id}): {ex_story}")
                            
                    if not sent_ok:
                        # 2. Agar Saved Messages'dan forward qilish bo'lsa
                        if fwd_msg_id:
                            await client.forward_messages(ch_id, fwd_msg_id, 'me')
                        # 3. Oddiy matn
                        elif msg_text:
                            await client.send_message(ch_id, msg_text)
                        
                    success_count += 1
                except FloodWaitError as e:
                    logger.warning(f"FloodWait: {e.seconds} soniya kutilmoqda...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"Xabar/Hikoya yuborishda xatolik ({ch.get('title', ch_id)}): {e}")
                    fail_count += 1
                
                # Cheklovlardan himoyalanish uchun 2.5 soniya kutish
                await asyncio.sleep(2.5)
            
            await client.disconnect()
            
            total = user.get("total_sent_count", 0) + success_count
            import time
            db.update_user_fields(user_id, last_sent_time=time.time(), total_sent_count=total)
            
            interval_sec = max(1, user.get("interval_minutes", 2)) * 60
            await asyncio.sleep(interval_sec)
            
        except asyncio.CancelledError:
            logger.info(f"Broadcast to'xtatildi user_id={user_id}")
            break
        except Exception as e:
            logger.error(f"Broadcast xatosi user_id={user_id}: {e}")
            await asyncio.sleep(30)

def start_user_broadcast(user_id: int, bot_instance):
    stop_user_broadcast(user_id)
    db.update_user_fields(user_id, is_broadcasting=1)
    task = asyncio.create_task(broadcast_worker(user_id, bot_instance))
    broadcast_tasks[user_id] = task

def stop_user_broadcast(user_id: int):
    db.update_user_fields(user_id, is_broadcasting=0)
    task = broadcast_tasks.pop(user_id, None)
    if task and not task.done():
        task.cancel()
