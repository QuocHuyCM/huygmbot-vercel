"""
Chạy 1 LẦN DUY NHẤT trên máy local để tạo bảng trong Supabase, trước khi deploy.
Cách chạy:
    export DATABASE_URL="postgresql://...supabase connection string..."
    python setup_db.py
"""
import os
import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]

conn = psycopg2.connect(DATABASE_URL)
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS settings (
    chat_id TEXT PRIMARY KEY,
    check_bio INTEGER
)""")

c.execute("""CREATE TABLE IF NOT EXISTS groups (
    chat_id TEXT PRIMARY KEY
)""")

c.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id TEXT,
    chat_id TEXT,
    username TEXT,
    first_name TEXT,
    PRIMARY KEY (user_id, chat_id)
)""")

c.execute("""CREATE TABLE IF NOT EXISTS bio_whitelist (
    user_id TEXT PRIMARY KEY
)""")

c.execute("""CREATE TABLE IF NOT EXISTS muted_users (
    user_id TEXT,
    chat_id TEXT,
    first_name TEXT,
    username TEXT,
    until_date TEXT,
    ly_do TEXT,
    muted_at TEXT,
    PRIMARY KEY (user_id, chat_id)
)""")

conn.commit()
conn.close()
print("✅ Đã tạo xong các bảng trong Supabase.")
