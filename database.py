# database.py
import sqlite3
import threading
from datetime import datetime

db_lock = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect('casino_bot.db', timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0,
                last_bonus TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS roulette_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                result TEXT,
                win_amount REAL,
                timestamp TEXT
            )
        ''')
        conn.commit()

def get_balance(user_id):
    with db_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                return result[0]
            cursor.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, 0))
            conn.commit()
            return 0

def update_balance(user_id, amount):
    with db_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                new_balance = result[0] + amount
                cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
            else:
                new_balance = amount
                cursor.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, amount))
            conn.commit()
            return new_balance

def set_bonus_time(user_id):
    with db_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET last_bonus = ? WHERE user_id = ?', 
                          (datetime.now().isoformat(), user_id))
            conn.commit()

def get_bonus_time(user_id):
    with db_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT last_bonus FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None

def add_roulette_log(user_id, result, win_amount):
    with db_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO roulette_history (user_id, result, win_amount, timestamp) VALUES (?, ?, ?, ?)',
                          (user_id, result, win_amount, datetime.now().isoformat()))
            conn.commit()
