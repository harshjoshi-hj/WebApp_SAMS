import hashlib
import os
import streamlit as st
import psycopg2
from database import connect

def hash_password(password):
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt.hex() + pwd_hash.hex()

def verify_password(stored_password, provided_password):
    try:
        salt = bytes.fromhex(stored_password[:32])
        stored_hash = bytes.fromhex(stored_password[32:])
        new_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode(), salt, 100000)
        return new_hash == stored_hash
    except Exception:
        return False

def login_user(username, password):
    conn = connect()
    if conn is None: return None
    cur = conn.cursor()
    try:
        cur.execute("SELECT password_hash, role FROM users WHERE username = %s", (username,))
        record = cur.fetchone()
        if record:
            stored_hash, role = record
            if verify_password(stored_hash, password):
                return role
        return None
    except Exception as e:
        print(f"Login Error: {e}")
        return None
    finally:
        conn.close()

def create_user(username, password, role="user"):
    conn = connect()
    if not conn: return False
    password_hash = hash_password(password)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", 
                    (username, password_hash, role))
        conn.commit()
        st.cache_data.clear() # ✅ Clear ALL cache to be safe and ensure new user appears
        return True
    except Exception as e:
        print(f"Create User Error: {e}")
        return False
    finally:
        conn.close()

def change_user_password(user_id, new_raw_password):
    conn = connect()
    if not conn: return False
    new_hash = hash_password(new_raw_password)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error changing password: {e}")
        return False
    finally:
        conn.close()