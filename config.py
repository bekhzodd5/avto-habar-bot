import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8287911559:AAFNSQIlHGi35lgoCPAoS1UpUTXYnISFbMo")

# Standart Telegram API (my.telegram.org)
API_ID = int(os.getenv("API_ID", "2040"))
API_HASH = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")

# Admin ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "7414653407"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
DB_PATH = os.path.join(BASE_DIR, "bot_database.sqlite3")

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# 1-2-3 rasmlardagi barcha Premium Emojilar ID ro'yxati
PREMIUM_EMOJIS = {
    "wave": "5472055112702629499",       # 1. 👋
    "link": "5211146110147521596",       # 2. 🔗
    "alert": "5210778929098424490",      # 3. ‼️
    "rocket": "5211001739116834909",     # 4. 🚀
    "plus": "5210864450487223671",       # 5. ➕
    "doc": "5839323457015256759",        # 6. 📄
    "speaker": "5771695636411847302",    # 7. 📢
    "loading": "5211004247377736463",    # 8. ⏳
    "write": "5458382591121964689",      # 9. ✍️
    "stats": "5884161133174067365",      # 10. 📊
    "user": "5886412370347036129",       # 11. 👤
    "phone": "5967591100532134862",      # 12. ☎️
    "camera": "5890744068203352126",     # 13. 📷
    "back": "5220157436865841975",       # 14. ⏪
    "num1": "5305763715692377402",       # 15. 1️⃣
    "num2": "5307907239380528763",       # 16. 2️⃣
    "cross": "4990519099055408115",      # 17. ❌
    "warning": "5211150061517435176",    # 18. ⚠️
    "hourglass": "4987817392827532337",  # 19. ⌛️
    "mail": "5967280668885913944",       # 20. ✉️
    "gem": "5210913477538901257",        # 21. 🔮
    "checkbox_off": "5890942929484123460", # 22. 🔲
    "lock": "5210852231305259632",       # 23. 🔐
    "star": "5469641199348363998",       # 24. ⭐️
    "image": "5931629923478278721",      # 25. 🖼
    "folder": "5433653135799228968",     # 26. 📁
    "check": "6296577138615125756",      # 27. ✅
    "gear": "5210775544664191769",       # 28. ⚙️
    "clipboard": "5264978435666642793",  # 29. 📋
    "tabs": "5211116985974287200",       # 30. 🗂
    "save": "5462956611033117422",       # 31. 💾
    "logout": "5877341274863832725",     # 32. 🚪
    "dot_green": "4990298741463319592",  # 33. 🟢
    "duck": "5474371208176737086",       # 34. 🐥
    "timer": "5215484787325676090",      # 35. ⏱
    "bulb": "5472146462362048818",       # 36. 💡
    "globe": "5879585266426973039",      # 37. 🌐
}

def emo(key: str, fallback: str = "") -> str:
    """Premium Custom Emoji HTML tegini qaytaradi"""
    eid = PREMIUM_EMOJIS.get(key)
    if eid:
        return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'
    return fallback
