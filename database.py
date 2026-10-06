import sqlite3
import json
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            session_string TEXT,
            phone TEXT,
            first_name TEXT,
            username TEXT,
            selected_channels TEXT DEFAULT '[]',
            interval_minutes INTEGER DEFAULT 2,
            is_broadcasting INTEGER DEFAULT 0,
            broadcast_msg_text TEXT,
            broadcast_msg_entities TEXT DEFAULT '[]',
            broadcast_forward_chat_id INTEGER,
            broadcast_forward_msg_id INTEGER,
            last_sent_time REAL DEFAULT 0,
            total_sent_count INTEGER DEFAULT 0,
            broadcast_type TEXT DEFAULT 'post',
            broadcast_story_url TEXT
        )
    ''')
    # Yangi ustunlarni mavjud bazaga xavfsiz qo'shish
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN broadcast_type TEXT DEFAULT 'post'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN broadcast_story_url TEXT")
    except Exception:
        pass
        
    conn.commit()
    conn.close()

def get_user(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "user_id": row[0],
        "session_string": row[1],
        "phone": row[2],
        "first_name": row[3],
        "username": row[4],
        "selected_channels": json.loads(row[5] or '[]'),
        "interval_minutes": row[6],
        "is_broadcasting": row[7],
        "broadcast_msg_text": row[8],
        "broadcast_msg_entities": json.loads(row[9] or '[]'),
        "broadcast_forward_chat_id": row[10],
        "broadcast_forward_msg_id": row[11],
        "last_sent_time": row[12],
        "total_sent_count": row[13],
        "broadcast_type": row[14] if len(row) > 14 and row[14] else "post",
        "broadcast_story_url": row[15] if len(row) > 15 else None
    }

def save_user_session(user_id: int, session_string: str, phone: str = None, first_name: str = None, username: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, session_string, phone, first_name, username)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            session_string=excluded.session_string,
            phone=excluded.phone,
            first_name=excluded.first_name,
            username=excluded.username
    ''', (user_id, session_string, phone, first_name, username))
    conn.commit()
    conn.close()

def delete_user_session(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET session_string = NULL,
            phone = NULL,
            first_name = NULL,
            username = NULL,
            is_broadcasting = 0
        WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()

def update_user_fields(user_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    
    set_clauses = []
    params = []
    for key, value in kwargs.items():
        if key in ["selected_channels", "broadcast_msg_entities"] and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        set_clauses.append(f"{key} = ?")
        params.append(value)
    params.append(user_id)
    
    query = f"UPDATE users SET {', '.join(set_clauses)} WHERE user_id = ?"
    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()

def get_active_broadcasters():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE is_broadcasting = 1 AND session_string IS NOT NULL')
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

init_db()
