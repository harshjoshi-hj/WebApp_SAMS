import streamlit as st
import psycopg2

# --- DATABASE CONNECTION ---
def connect():
    try:
        db_config = st.secrets["connections"]["postgresql"]
        return psycopg2.connect(
            host=db_config["host"],
            user=db_config["username"],
            password=db_config["password"],
            port=db_config["port"],
            dbname=db_config["database"],
            sslmode='require'
        )
    except Exception as e:
        st.error(f"Cloud Connection Error: {e}")
        return None

# --- READ HELPER FUNCTIONS (⚡ CACHED) ---

@st.cache_data(ttl=60)
def get_dashboard_stats():
    conn = connect()
    if not conn: return {}
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM assets")
        sub_total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM assets WHERE expiry_date < CURRENT_DATE")
        sub_expired = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM hardware")
        hw_total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM hardware WHERE status='Assigned'")
        hw_assigned = cur.fetchone()[0]
        return {
            "sub_total": sub_total, "sub_expired": sub_expired,
            "hw_total": hw_total, "hw_assigned": hw_assigned
        }
    except Exception: return {}
    finally: conn.close()

@st.cache_data(ttl=300)
def get_department_counts():
    conn = connect()
    if not conn: return {}
    try:
        cur = conn.cursor()
        cur.execute("SELECT department, COUNT(*) FROM assets GROUP BY department")
        return dict(cur.fetchall())
    except Exception: return {}
    finally: conn.close()

@st.cache_data(ttl=60)
def get_hardware_status_counts():
    conn = connect()
    if not conn: return {}
    try:
        cur = conn.cursor()
        cur.execute("SELECT status, COUNT(*) FROM hardware GROUP BY status")
        return dict(cur.fetchall())
    except Exception: return {}
    finally: conn.close()

@st.cache_data(ttl=60)
def get_all_staff():
    conn = connect()
    if not conn: return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, full_name, username FROM staff")
        return cur.fetchall()
    except Exception: return []
    finally: conn.close()

@st.cache_data(ttl=60)
def get_all_users():
    conn = connect()
    if not conn: return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, role FROM users ORDER BY id ASC")
        return cur.fetchall()
    except Exception: return []
    finally: conn.close()

# --- ASSET FUNCTIONS (The missing part!) ---

def add_asset(item, ref, expiry, cat, dept, supp):
    conn = connect()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO assets (item_name, reference_no, expiry_date, category, department, supplier) VALUES (%s, %s, %s, %s, %s, %s)", 
                    (item, ref, expiry, cat, dept, supp))
        conn.commit()
        get_dashboard_stats.clear()
        return True
    except Exception: return False
    finally: conn.close()

def delete_asset(asset_id):
    conn = connect()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
        conn.commit()
        get_dashboard_stats.clear()
        return True
    except Exception as e:
        print(f"Error deleting asset: {e}")
        return False
    finally:
        conn.close()

def update_asset(asset_id, item, ref, expiry, cat, dept, supp):
    conn = connect()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE assets 
            SET item_name=%s, reference_no=%s, expiry_date=%s, category=%s, department=%s, supplier=%s 
            WHERE id=%s
        """, (item, ref, expiry, cat, dept, supp, asset_id))
        conn.commit()
        get_dashboard_stats.clear()
        return True
    except Exception as e:
        print(f"Error updating asset: {e}")
        return False
    finally:
        conn.close()

# --- STAFF FUNCTIONS ---

def add_staff_member(name, user, email, phone, gender, dob, created_by_user):
    conn = connect()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO staff (full_name, username, email, phone, gender, dob, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                    (name, user, email, phone, gender, dob, created_by_user))
        conn.commit()
        get_all_staff.clear()
        return True
    except Exception: return False
    finally: conn.close()

def delete_staff(staff_id):
    conn = connect()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("UPDATE hardware SET assigned_to_id = NULL, status = 'Available' WHERE assigned_to_id = %s", (staff_id,))
        cur.execute("DELETE FROM staff WHERE id = %s", (staff_id,))
        conn.commit()
        get_all_staff.clear()
        return True
    except Exception: return False
    finally: conn.close()

# --- HARDWARE FUNCTIONS ---

def add_hardware(name, serial, model, status):
    conn = connect()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO hardware (item_name, serial_no, model, status) VALUES (%s, %s, %s, %s)", 
                    (name, serial, model, status))
        conn.commit()
        get_dashboard_stats.clear()
        get_hardware_status_counts.clear()
        return True
    except Exception: return False
    finally: conn.close()

def delete_hardware(hw_id):
    conn = connect()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM hardware WHERE id = %s", (hw_id,))
        conn.commit()
        get_dashboard_stats.clear()
        return True
    except Exception: return False
    finally: conn.close()

def update_hardware_status(hw_id, new_status, assigned_to_id=None):
    conn = connect()
    if not conn: return False
    try:
        cur = conn.cursor()
        if assigned_to_id:
            cur.execute("UPDATE hardware SET status = %s, assigned_to_id = %s, assigned_date = CURRENT_DATE WHERE id = %s", 
                        (new_status, assigned_to_id, hw_id))
        else:
            cur.execute("UPDATE hardware SET status = %s, assigned_to_id = NULL, assigned_date = NULL WHERE id = %s", 
                        (new_status, hw_id))
        conn.commit()
        get_hardware_status_counts.clear()
        return True
    except Exception: return False
    finally: conn.close()

# --- USER FUNCTIONS ---

def delete_user(user_id):
    conn = connect()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        get_all_users.clear()
        return True
    except Exception: return False
    finally: conn.close()

def update_user_role(user_id, new_role):
    conn = connect()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        conn.commit()
        get_all_users.clear()
        return True
    except Exception: return False
    finally: conn.close()