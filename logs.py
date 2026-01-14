import streamlit as st
import socket
from requests import get
from database import connect

def get_client_ip():
    """Robust IP detection for Local and Cloud."""
    try:
        # 1. Cloud / Proxy (Best for deployed apps)
        if st.context.headers:
            x_forwarded_for = st.context.headers.get("X-Forwarded-For")
            if x_forwarded_for:
                return x_forwarded_for.split(",")[0]
        
        # 2. External Public IP (Needs Internet)
        try:
            public_ip = get('https://api.ipify.org', timeout=1).text
            return public_ip
        except:
            pass

        # 3. Local Network IP (Best for Mac/Windows local dev)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't actually connect, just gets the IP route
            s.connect(('8.8.8.8', 1))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()
        return local_ip

    except Exception:
        return "Unknown"

def log_action(user, action, target="", old_value=None, new_value=None):
    conn = connect()
    if conn is None: return

    ip_address = get_client_ip()

    details = None
    if old_value or new_value:
        details = f"Changed from: [{old_value}] TO: [{new_value}]"

    try:
        cur = conn.cursor()
        query = """
            INSERT INTO logs ("user", action, target, ip_address, details) 
            VALUES (%s, %s, %s, %s, %s)
        """
        cur.execute(query, (user, action, target, ip_address, details))
        conn.commit()
    except Exception as e:
        print(f"Logging Error: {e}")
    finally:
        conn.close()