import streamlit as st
import pandas as pd
import time
import bcrypt
from datetime import datetime, timedelta
from supabase import create_client

# --- ⚙️ CONFIGURATION ---
DB_PASS_COL = "password_hash" 

st.set_page_config(page_title="LS Cable - IMS", page_icon="📦", layout="wide")

# --- 🔌 CONNECT TO SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Secret Error: {e}")
        return None

supabase = init_connection()

# --- 🛠 HELPER FUNCTIONS ---
def hash_password(plain_text_password):
    return bcrypt.hashpw(plain_text_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(plain_text_password, hashed_password):
    try:
        return bcrypt.checkpw(plain_text_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except:
        return False

def log_action(user, action, target):
    try:
        data = {
            "user": user,
            "action": action,
            "target": target,
            "timestamp": pd.Timestamp.now().isoformat()
        }
        supabase.table("logs").insert(data).execute()
    except Exception as e:
        print(f"Log Error: {e}")

def get_data(table_name):
    try:
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except:
        return pd.DataFrame()

def login_user(username, password):
    try:
        response = supabase.table("users").select("*").eq("username", username).execute()
        if response.data:
            user = response.data[0]
            stored_pw = user.get(DB_PASS_COL)
            if not stored_pw: return None

            try:
                if bcrypt.checkpw(password.encode('utf-8'), stored_pw.encode('utf-8')):
                    return user['role']
            except (ValueError, TypeError):
                pass

            if stored_pw == password:
                new_hash = hash_password(password)
                supabase.table("users").update({DB_PASS_COL: new_hash}).eq("username", username).execute()
                return user['role']
    except Exception as e:
        print(f"Login Error: {e}")
    return None

def update_password(username, new_password):
    try:
        hashed_pw = hash_password(new_password)
        supabase.table("users").update({DB_PASS_COL: hashed_pw}).eq("username", username).execute()
        log_action(st.session_state.get('username'), "Update Password", username)
        return True
    except:
        return False

# --- ⏳ SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'role' not in st.session_state: st.session_state['role'] = ""
if 'selected_ticket' not in st.session_state: st.session_state['selected_ticket'] = None

# --- DIALOGS ---
@st.dialog("⚠️ Confirm Deletion")
def confirm_delete(table, id_list):
    st.write(f"Are you sure you want to delete {len(id_list)} items?")
    if st.button("Confirm Delete", type="primary"):
        for item_id in id_list:
            supabase.table(table).delete().eq("id", item_id).execute()
        log_action(st.session_state.get('username'), "Bulk Delete", table)
        st.success("Deleted!")
        time.sleep(1)
        st.rerun()

@st.dialog("Submit Support Ticket")
def create_ticket_form():
    with st.form("new_ticket_form"):
        subject = st.text_input("Subject / Issue Title", placeholder="e.g., Login Error")
        message = st.text_area("Message", placeholder="Describe your issue...", height=150)
        
        if st.form_submit_button("Submit Ticket", type="primary"):
            if subject and message:
                try:
                    data = {
                        "subject": subject, 
                        "initial_message": message,
                        "created_by": st.session_state['username'],
                        "status": "Open",
                        "created_at": pd.Timestamp.now().isoformat()
                    }
                    res = supabase.table("tickets").insert(data).execute()
                    if res.data:
                        tid = res.data[0]['id']
                        supabase.table("ticket_replies").insert({
                            "ticket_id": tid,
                            "sender": st.session_state['username'],
                            "message": message
                        }).execute()
                    st.success("Ticket Created!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please fill all fields.")

# --- UI COMPONENTS ---
def login_page():
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.title("📦 LS Cable IMS")
        st.subheader("Login")
        user = st.text_input("Username")
        pw = st.text_input("Password") 
        if st.button("Login", use_container_width=True):
            role = login_user(user, pw)
            if role:
                st.session_state['logged_in'] = True
                st.session_state['username'] = user
                st.session_state['role'] = role
                log_action(user, "Login", "Web Access")
                st.rerun()
            else:
                st.error("Invalid credentials")

def render_ticket_row(t):
    """Renders a single ticket row safely."""
    try:
        with st.container():
            col_id, col_stat, col_sub, col_user, col_act = st.columns([0.5, 1, 3, 1.5, 1])
            
            # Use .get() to prevent crashes if data is missing
            t_id = t.get('id', '??')
            t_status = t.get('status', 'Open')
            t_subj = t.get('subject', 'No Subject')
            t_creator = t.get('created_by', 'Unknown')
            t_date = str(t.get('created_at', ''))[:10]

            col_id.write(f"**#{t_id}**")
            
            color = "green" if t_status == 'Open' else "grey" if t_status == 'Closed' else "orange"
            col_stat.markdown(f":{color}[{t_status}]")
            
            col_sub.write(t_subj)
            col_user.caption(f"{t_creator}\n{t_date}")
            
            if col_act.button("View", key=f"btn_{t_id}"):
                st.session_state['selected_ticket'] = t
                st.rerun()
            st.divider()
    except Exception as e:
        st.error(f"Row Error: {e}")

def render_ticket_detail(ticket, is_admin):
    if st.button("← Back to List"):
        st.session_state['selected_ticket'] = None
        st.rerun()
    
    t_subj = ticket.get('subject', 'No Subject')
    t_id = ticket.get('id', '?')
    t_creator = ticket.get('created_by', 'Unknown')
    t_date = ticket.get('created_at', '')
    t_status = ticket.get('status', 'Open')

    st.markdown(f"### {t_subj} <span style='color:grey; font-size:0.8em'>#{t_id}</span>", unsafe_allow_html=True)
    st.caption(f"Created by **{t_creator}** on {t_date}")
    st.write(f"**Status:** {t_status}")
    st.divider()

    replies = []
    try:
        r_res = supabase.table("ticket_replies").select("*").eq("ticket_id", t_id).order("created_at", desc=False).execute()
        replies = r_res.data
    except: pass

    chat_container = st.container(height=400)
    with chat_container:
        for r in replies:
            sender = r.get('sender', 'Unknown')
            msg = r.get('message', '')
            is_me = sender == st.session_state['username']
            role_icon = "🛠️" if "admin" in sender or (is_admin and is_me) else "👤"
            with st.chat_message(sender, avatar=role_icon):
                st.write(msg)
                st.caption(str(r.get('created_at', '')))

    with st.form("reply_form"):
        st.write("Reply")
        new_msg = st.text_area("Message", height=100, label_visibility="collapsed")
        
        new_status = t_status
        if is_admin:
            c_stat, _ = st.columns([1, 2])
            # Handle case where status might not be in list
            idx = 0
            opts = ["Open", "In Progress", "Closed"]
            if t_status in opts: idx = opts.index(t_status)
            new_status = c_stat.selectbox("Update Status", opts, index=idx)
        
        if st.form_submit_button("Send Reply"):
            if new_msg:
                supabase.table("ticket_replies").insert({
                    "ticket_id": t_id,
                    "sender": st.session_state['username'],
                    "message": new_msg
                }).execute()
                
                if is_admin and new_status != t_status:
                    supabase.table("tickets").update({"status": new_status}).eq("id", t_id).execute()
                    # Update local state
                    st.session_state['selected_ticket']['status'] = new_status
                
                st.success("Sent!")
                st.rerun()

# --- SUPPORT MODULE ---
def support_module():
    st.title("📢 Support Portal")
    is_admin = st.session_state['role'] == 'admin'

    if st.session_state['selected_ticket'] is not None:
        render_ticket_detail(st.session_state['selected_ticket'], is_admin)
    else:
        # 1. Admin Dashboard
        if is_admin:
            st.subheader("🛠️ Admin Support Dashboard")
            c_date, c_btn = st.columns([3, 1])
            with c_date:
                default_start = datetime.now() - timedelta(days=30)
                date_range = st.date_input("Filter by Date", value=(default_start, datetime.now()))
            with c_btn:
                if st.button("➕ Create Ticket"):
                    create_ticket_form()
            
            # Fetch All Tickets
            try:
                response = supabase.table("tickets").select("*").order("created_at", desc=True).execute()
                df_tickets = pd.DataFrame(response.data)
                
                if not df_tickets.empty:
                    # Apply Date Filter
                    if len(date_range) == 2:
                        start_d, end_d = date_range
                        if 'created_at' in df_tickets.columns:
                            # Safely convert to datetime
                            df_tickets['created_at'] = pd.to_datetime(df_tickets['created_at'], errors='coerce')
                            # Drop invalid dates if any
                            df_tickets = df_tickets.dropna(subset=['created_at'])
                            # Filter
                            mask = (df_tickets['created_at'].dt.date >= start_d) & (df_tickets['created_at'].dt.date <= end_d)
                            df_filtered = df_tickets[mask]
                        else:
                            df_filtered = df_tickets
                    else:
                        df_filtered = df_tickets

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Tickets", len(df_filtered))
                    m2.metric("Open Tickets", len(df_filtered[df_filtered['status'] == 'Open']) if 'status' in df_filtered.columns else 0)
                    m3.download_button("⬇️ Download Report", df_filtered.to_csv(index=False).encode('utf-8'), "support_report.csv")
                    
                    st.divider()
                    st.write("### Ticket History")
                    for idx, t in df_filtered.iterrows():
                        render_ticket_row(t)
                else:
                    st.info("No tickets found in database.")
            except Exception as e:
                st.error(f"Error Loading Admin Tickets: {e}")

        # 2. User Dashboard
        else:
            c1, c2 = st.columns([3, 1])
            c1.subheader("Your Tickets")
            if c2.button("➕ Create New Ticket"):
                create_ticket_form()
            
            try:
                response = supabase.table("tickets").select("*").eq("created_by", st.session_state['username']).order("created_at", desc=True).execute()
                df_tickets = pd.DataFrame(response.data)
                
                if not df_tickets.empty:
                    for idx, t in df_tickets.iterrows():
                        render_ticket_row(t)
                else:
                    st.info("You haven't created any tickets yet.")
            except Exception as e:
                # THIS WILL SHOW THE REAL ERROR INSTEAD OF "Connection Error"
                st.error(f"Error Loading User Tickets: {e}")

# --- MAIN APP ---
def main_app():
    st.sidebar.title(f"👤 {st.session_state['username']}")
    st.sidebar.caption(f"Role: {st.session_state['role']}")
    role = st.session_state['role']
    
    if role == 'admin':
        menu = st.sidebar.radio("Menu", ["Dashboard", "Support", "Subscriptions", "Hardware", "Staff", "Users", "Logs"])
    else:
        menu = st.sidebar.radio("Menu", ["Support"])
        
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    if menu == "Dashboard" and role == 'admin':
        st.title("📊 System Dashboard")
        c_date, _ = st.columns([1, 2])
        with c_date:
            default_start = datetime.now() - timedelta(days=30)
            date_range = st.date_input("📅 Date Range for Reports", value=(default_start, datetime.now()))

        df_assets = get_data("assets")
        df_hw = get_data("hardware")
        df_logs = get_data("logs")
        
        if len(date_range) == 2:
            start_d, end_d = date_range
            if not df_logs.empty and 'timestamp' in df_logs.columns:
                df_logs['timestamp'] = pd.to_datetime(df_logs['timestamp']).dt.tz_localize(None)
                df_logs = df_logs[(df_logs['timestamp'].dt.date >= start_d) & (df_logs['timestamp'].dt.date <= end_d)]
            if not df_hw.empty and 'created_at' in df_hw.columns:
                df_hw['created_at'] = pd.to_datetime(df_hw['created_at']).dt.tz_localize(None)
                df_hw_filtered = df_hw[(df_hw['created_at'].dt.date >= start_d) & (df_hw['created_at'].dt.date <= end_d)]
            else:
                df_hw_filtered = df_hw

        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Subscriptions", len(df_assets))
        c2.metric("💻 Hardware", len(df_hw))
        c3.metric("📜 Logs", len(df_logs))
        
        st.divider()
        st.subheader("📥 Reports")
        r1, r2, r3 = st.columns(3)
        if not df_hw.empty:
            r1.download_button("⬇️ Hardware CSV", df_hw.to_csv(index=False).encode('utf-8'), "hw_report.csv")
        if not df_assets.empty:
            r2.download_button("⬇️ Software CSV", df_assets.to_csv(index=False).encode('utf-8'), "sw_report.csv")
        if not df_logs.empty:
            r3.download_button("⬇️ Logs CSV", df_logs.to_csv(index=False).encode('utf-8'), "logs_filtered.csv")

    elif menu == "Support":
        support_module()

    elif menu == "Subscriptions" and role == 'admin':
        st.title("📄 Subscriptions")
        df = get_data("assets")
        tab1, tab2 = st.tabs(["View / Search", "Add & Upload"])
        with tab1:
            if not df.empty:
                search = st.text_input("Search Assets")
                if search:
                    df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
                df.insert(0, "Select", False)
                edited = st.data_editor(df, hide_index=True)
                if st.button("Delete Selected Assets"):
                    selected = edited[edited.Select]
                    if not selected.empty:
                        confirm_delete("assets", selected['id'].tolist())
            else:
                st.info("No subscriptions found.")
        with tab2:
            st.subheader("Manual Entry")
            with st.form("add_asset"):
                c1, c2 = st.columns(2)
                item = c1.text_input("Item Name")
                ref = c2.text_input("Reference No")
                exp = c1.date_input("Expiry Date")
                cat = c2.selectbox("Category", ["Software", "License", "Domain"])
                dept = c1.selectbox("Department", ["IT", "HR", "Sales"])
                sup = c2.text_input("Supplier")
                if st.form_submit_button("Save"):
                    data = {"item_name": item, "reference_no": ref, "expiry_date": str(exp), "category": cat, "department": dept, "supplier": sup}
                    supabase.table("assets").insert(data).execute()
                    st.success("Saved!")
                    st.rerun()
            st.divider()
            st.subheader("📂 Bulk Upload")
            c_dl, c_up = st.columns([1, 2])
            with c_dl:
                sample = pd.DataFrame([{"item_name": "Office 365", "reference_no": "MS-101", "expiry_date": "2026-12-31", "category": "Software", "department": "IT", "supplier": "Microsoft"}])
                st.download_button("⬇️ Template", sample.to_csv(index=False).encode('utf-8'), "sub_template.csv")
            with c_up:
                up_file = st.file_uploader("Upload CSV", type=['csv'], key='sub_csv')
                if up_file and st.button("Process Bulk"):
                    try:
                        data = pd.read_csv(up_file)
                        records = data.to_dict('records')
                        for r in records: r['expiry_date'] = str(r['expiry_date'])
                        supabase.table("assets").insert(records).execute()
                        st.success("Uploaded!")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    elif menu == "Hardware" and role == 'admin':
        st.title("💻 Hardware Inventory")
        df = get_data("hardware")
        tab1, tab2 = st.tabs(["Inventory", "Add & Upload"])
        with tab1:
            if not df.empty:
                df.insert(0, "Select", False)
                edited = st.data_editor(df, hide_index=True)
                if st.button("Delete Selected Hardware"):
                    selected = edited[edited.Select]
                    if not selected.empty:
                        confirm_delete("hardware", selected['id'].tolist())
            else:
                st.info("No hardware found.")
        with tab2:
            st.subheader("Manual Entry")
            with st.form("add_hw"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Item Name")
                serial = c2.text_input("Serial No")
                model = c1.text_input("Model")
                stat = c2.selectbox("Status", ["Available", "Assigned", "Broken"])
                if st.form_submit_button("Add"):
                    supabase.table("hardware").insert({"item_name": name, "serial_no": serial, "model": model, "status": stat}).execute()
                    st.success("Added!")
                    st.rerun()
            st.divider()
            st.subheader("📂 Bulk Upload")
            c_dl, c_up = st.columns([1, 2])
            with c_dl:
                sample = pd.DataFrame([{"item_name": "Dell XPS", "serial_no": "SN-001", "model": "XPS-15", "status": "Available"}])
                st.download_button("⬇️ Template", sample.to_csv(index=False).encode('utf-8'), "hw_template.csv")
            with c_up:
                up_file = st.file_uploader("Upload CSV", type=['csv'], key='hw_csv')
                if up_file and st.button("Process Bulk"):
                    try:
                        data = pd.read_csv(up_file)
                        records = data.to_dict('records')
                        supabase.table("hardware").insert(records).execute()
                        st.success("Uploaded!")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    elif menu == "Staff" and role == 'admin':
        st.title("👥 Staff Directory")
        df = get_data("staff")
        tab1, tab2 = st.tabs(["Directory", "Add & Upload"])
        with tab1:
            if not df.empty:
                df.insert(0, "Select", False)
                edited = st.data_editor(df, hide_index=True)
                if st.button("Delete Selected Staff"):
                    selected = edited[edited.Select]
                    if not selected.empty:
                        confirm_delete("staff", selected['id'].tolist())
            else:
                st.info("No staff found.")
        with tab2:
            with st.form("add_staff"):
                name = st.text_input("Full Name")
                email = st.text_input("Email")
                if st.form_submit_button("Save"):
                    supabase.table("staff").insert({"full_name": name, "email": email}).execute()
                    st.success("Saved!")
                    st.rerun()
            st.divider()
            st.subheader("📂 Bulk Upload")
            c_dl, c_up = st.columns([1, 2])
            with c_dl:
                sample = pd.DataFrame([{"full_name": "John Doe", "email": "john@example.com"}])
                st.download_button("⬇️ Template", sample.to_csv(index=False).encode('utf-8'), "staff_tpl.csv")
            with c_up:
                up_file = st.file_uploader("Upload CSV", type=['csv'], key='st_csv')
                if up_file and st.button("Process Staff"):
                    try:
                        data = pd.read_csv(up_file)
                        supabase.table("staff").insert(data.to_dict('records')).execute()
                        st.success("Uploaded!")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    elif menu == "Users" and role == 'admin':
        st.title("🔐 User Management")
        df = get_data("users")
        tab1, tab2, tab3, tab4 = st.tabs(["List Users", "Create User", "Bulk Upload", "Change Password"])
        
        with tab1:
            if not df.empty:
                display_df = df.drop(columns=[DB_PASS_COL], errors='ignore')
                st.dataframe(display_df, use_container_width=True)
            else:
                st.info("No users found.")
            
        with tab2:
            st.subheader("Create New User")
            with st.form("new_user"):
                u = st.text_input("Username")
                p = st.text_input("Password (Visible)", type="default")
                r = st.selectbox("Role", ["admin", "user", "manager"])
                if st.form_submit_button("Create User"):
                    try:
                        hashed = hash_password(p)
                        data = {"username": u, DB_PASS_COL: hashed, "role": r}
                        supabase.table("users").insert(data).execute()
                        st.success("User Created!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        with tab3:
            st.subheader("📂 Bulk Upload Users")
            c_dl, c_up = st.columns([1, 2])
            with c_dl:
                sample = pd.DataFrame([{"username": "user1", "password": "pw1", "role": "user"}])
                st.download_button("⬇️ Template", sample.to_csv(index=False).encode('utf-8'), "user_tpl.csv")
            with c_up:
                up_file = st.file_uploader("Upload CSV", type=['csv'], key='us_csv')
                if up_file and st.button("Process Users"):
                    try:
                        data = pd.read_csv(up_file)
                        records = []
                        for _, row in data.iterrows():
                            rec = row.to_dict()
                            if 'password' in rec:
                                rec[DB_PASS_COL] = hash_password(str(rec['password']))
                                if DB_PASS_COL != 'password':
                                    del rec['password']
                            records.append(rec)
                        supabase.table("users").insert(records).execute()
                        st.success(f"Created {len(records)} users!")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

        with tab4:
            st.subheader("Update User Password")
            if not df.empty:
                target_user = st.selectbox("Select User", df['username'].tolist())
                new_pass = st.text_input("New Password", type="default")
                if st.button("Update Password"):
                    if update_password(target_user, new_pass):
                        st.success(f"Password for {target_user} updated!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to update.")

    elif menu == "Logs" and role == 'admin':
        st.title("📜 Audit Logs")
        df = get_data("logs")
        if not df.empty:
            st.dataframe(df.sort_values(by="timestamp", ascending=False), use_container_width=True)

# --- EXECUTION START ---
if st.session_state['logged_in']:
    main_app()
else:
    login_page()