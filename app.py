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

# --- 🟢 DIALOGS (POPUPS) ---

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
        subject = st.text_input("Subject / Issue Title")
        message = st.text_area("Message")
        if st.form_submit_button("Submit Ticket", type="primary"):
            if subject and message:
                try:
                    data = {"subject": subject, "initial_message": message, "created_by": st.session_state['username'], "status": "Open", "created_at": pd.Timestamp.now().isoformat()}
                    res = supabase.table("tickets").insert(data).execute()
                    if res.data:
                        tid = res.data[0]['id']
                        supabase.table("ticket_replies").insert({"ticket_id": tid, "sender": st.session_state['username'], "message": message}).execute()
                    st.success("Ticket Created!")
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

# --- ✏️ EDIT POPUPS ---

@st.dialog("✏️ Edit Hardware")
def edit_hardware_dialog(item):
    st.caption(f"Editing: {item.get('item_name', 'Unknown')}")
    with st.form("edit_hw_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Item Name", value=item.get("item_name", ""))
        serial = c2.text_input("Serial No", value=item.get("serial_no", ""))
        model = c1.text_input("Model", value=item.get("model", ""))
        asset_code = c2.text_input("Asset Code", value=item.get("asset_code", ""))
        
        # Handle Date
        d_val = None
        if item.get("capitalized_date"):
            try: d_val = pd.to_datetime(item.get("capitalized_date")).date()
            except: pass
        cap_date = c1.date_input("Capitalized Date", value=d_val)
        
        # Handle Status
        status_opts = ["Available", "Assigned", "Broken"]
        curr_stat = item.get("status", "Available")
        idx = status_opts.index(curr_stat) if curr_stat in status_opts else 0
        stat = c2.selectbox("Status", status_opts, index=idx)
        
        if st.form_submit_button("Update Hardware"):
            update_data = {
                "item_name": name, "serial_no": serial, "model": model, 
                "asset_code": asset_code, "status": stat
            }
            if cap_date: update_data["capitalized_date"] = str(cap_date)
            
            supabase.table("hardware").update(update_data).eq("id", item["id"]).execute()
            st.success("Updated Successfully!")
            st.rerun()

@st.dialog("✏️ Edit Subscription")
def edit_asset_dialog(item):
    st.caption(f"Editing: {item.get('item_name', '')}")
    with st.form("edit_sub_form"):
        c1, c2 = st.columns(2)
        item_name = c1.text_input("Item Name", value=item.get("item_name", ""))
        ref = c2.text_input("Reference No", value=item.get("reference_no", ""))
        
        d_val = None
        if item.get("expiry_date"):
            try: d_val = pd.to_datetime(item.get("expiry_date")).date()
            except: pass
        exp = c1.date_input("Expiry Date", value=d_val)
        
        cat_opts = ["Software", "License", "Domain"]
        cat_idx = cat_opts.index(item.get("category")) if item.get("category") in cat_opts else 0
        cat = c2.selectbox("Category", cat_opts, index=cat_idx)
        
        dept_opts = ["IT", "HR", "Sales"]
        dept_idx = dept_opts.index(item.get("department")) if item.get("department") in dept_opts else 0
        dept = c1.selectbox("Department", dept_opts, index=dept_idx)
        
        sup = c2.text_input("Supplier", value=item.get("supplier", ""))
        
        if st.form_submit_button("Update Subscription"):
            update_data = {
                "item_name": item_name, "reference_no": ref, "category": cat,
                "department": dept, "supplier": sup
            }
            if exp: update_data["expiry_date"] = str(exp)
            supabase.table("assets").update(update_data).eq("id", item["id"]).execute()
            st.success("Updated!")
            st.rerun()

@st.dialog("✏️ Edit Staff")
def edit_staff_dialog(item):
    st.caption(f"Editing: {item.get('full_name', '')}")
    with st.form("edit_staff_form"):
        name = st.text_input("Full Name", value=item.get("full_name", ""))
        email = st.text_input("Email", value=item.get("email", ""))
        dept = st.text_input("Department", value=item.get("department", ""))
        emp_no = st.text_input("Employee Number", value=item.get("employee_number", ""))
        
        d_val = None
        if item.get("doj"):
            try: d_val = pd.to_datetime(item.get("doj")).date()
            except: pass
        doj = st.date_input("Date of Joining", value=d_val)
        
        if st.form_submit_button("Update Staff"):
            update_data = {"full_name": name, "email": email, "department": dept, "employee_number": emp_no}
            if doj: update_data["doj"] = str(doj)
            supabase.table("staff").update(update_data).eq("id", item["id"]).execute()
            st.success("Updated!")
            st.rerun()

@st.dialog("✏️ Edit User Role")
def edit_user_dialog(item):
    st.caption(f"Editing User: {item.get('username')}")
    with st.form("edit_user_form"):
        roles = ["admin", "user", "manager"]
        curr = item.get("role", "user")
        idx = roles.index(curr) if curr in roles else 1
        new_role = st.selectbox("Role", roles, index=idx)
        
        if st.form_submit_button("Update Role"):
            supabase.table("users").update({"role": new_role}).eq("id", item["id"]).execute()
            st.success("Role Updated!")
            st.rerun()

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
    try:
        with st.container():
            col_id, col_stat, col_sub, col_user, col_act = st.columns([0.5, 1, 3, 1.5, 1])
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
            idx = 0
            opts = ["Open", "In Progress", "Closed"]
            if t_status in opts: idx = opts.index(t_status)
            new_status = c_stat.selectbox("Update Status", opts, index=idx)
        if st.form_submit_button("Send Reply"):
            if new_msg:
                supabase.table("ticket_replies").insert({
                    "ticket_id": t_id, "sender": st.session_state['username'], "message": new_msg
                }).execute()
                if is_admin and new_status != t_status:
                    supabase.table("tickets").update({"status": new_status}).eq("id", t_id).execute()
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
        if is_admin:
            st.subheader("🛠️ Admin Support Dashboard")
            c_date, c_btn = st.columns([3, 1])
            with c_date:
                default_start = datetime.now() - timedelta(days=30)
                date_range = st.date_input("Filter by Date", value=(default_start, datetime.now()))
            with c_btn:
                if st.button("➕ Create Ticket"): create_ticket_form()
            try:
                response = supabase.table("tickets").select("*").order("created_at", desc=True).execute()
                df_tickets = pd.DataFrame(response.data)
                if not df_tickets.empty:
                    if len(date_range) == 2:
                        start_d, end_d = date_range
                        if 'created_at' in df_tickets.columns:
                            df_tickets['created_at'] = pd.to_datetime(df_tickets['created_at'], errors='coerce')
                            df_tickets = df_tickets.dropna(subset=['created_at'])
                            mask = (df_tickets['created_at'].dt.date >= start_d) & (df_tickets['created_at'].dt.date <= end_d)
                            df_filtered = df_tickets[mask]
                        else: df_filtered = df_tickets
                    else: df_filtered = df_tickets
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Tickets", len(df_filtered))
                    m2.metric("Open Tickets", len(df_filtered[df_filtered['status'] == 'Open']) if 'status' in df_filtered.columns else 0)
                    m3.download_button("⬇️ Download Report", df_filtered.to_csv(index=False).encode('utf-8'), "support_report.csv")
                    st.divider()
                    st.write("### Ticket History")
                    for idx, t in df_filtered.iterrows(): render_ticket_row(t)
                else: st.info("No tickets found in database.")
            except Exception as e: st.error(f"Error Loading Admin Tickets: {e}")
        else:
            c1, c2 = st.columns([3, 1])
            c1.subheader("Your Tickets")
            if c2.button("➕ Create New Ticket"): create_ticket_form()
            try:
                response = supabase.table("tickets").select("*").eq("created_by", st.session_state['username']).order("created_at", desc=True).execute()
                df_tickets = pd.DataFrame(response.data)
                if not df_tickets.empty:
                    for idx, t in df_tickets.iterrows(): render_ticket_row(t)
                else: st.info("You haven't created any tickets yet.")
            except Exception as e: st.error(f"Error Loading User Tickets: {e}")

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

    # --- DASHBOARD (UPDATED LAYOUT) ---
    if menu == "Dashboard" and role == 'admin':
        # Header Row: Title Left, Date Picker Right
        col_title, col_filter = st.columns([2, 1])
        with col_title:
            st.title("📊 System Dashboard")
        with col_filter:
            default_start = datetime.now() - timedelta(days=30)
            date_range = st.date_input("📅 Date Range", value=(default_start, datetime.now()))

        # Load Data
        df_assets = get_data("assets")
        df_hw = get_data("hardware")
        df_logs = get_data("logs")
        
        # Apply Date Filters
        if len(date_range) == 2:
            start_d, end_d = date_range
            if not df_logs.empty and 'timestamp' in df_logs.columns:
                df_logs['timestamp'] = pd.to_datetime(df_logs['timestamp']).dt.tz_localize(None)
                df_logs = df_logs[(df_logs['timestamp'].dt.date >= start_d) & (df_logs['timestamp'].dt.date <= end_d)]
            if not df_hw.empty and 'created_at' in df_hw.columns:
                df_hw['created_at'] = pd.to_datetime(df_hw['created_at']).dt.tz_localize(None)
                # Keep original hardware data for total count, but maybe filter for charts
                pass 

        # Metric Cards
        st.markdown("### Overview")
        m1, m2, m3 = st.columns(3)
        with m1:
            with st.container(border=True):
                st.metric("📦 Subscriptions", len(df_assets))
        with m2:
            with st.container(border=True):
                st.metric("💻 Hardware", len(df_hw))
        with m3:
            with st.container(border=True):
                st.metric("📜 Logs", len(df_logs))
        
        st.divider()

        # Charts and Reports
        c_charts, c_reports = st.columns([2, 1])
        
        with c_charts:
            st.subheader("📈 Analytics")
            tab1, tab2 = st.tabs(["Hardware Status", "Assets by Department"])
            with tab1:
                if not df_hw.empty:
                    # Simple bar chart of status
                    st.bar_chart(df_hw['status'].value_counts())
                else:
                    st.info("No data available")
            with tab2:
                if not df_assets.empty:
                    # Simple bar chart of departments
                    st.bar_chart(df_assets['department'].value_counts())
                else:
                    st.info("No data available")

        with c_reports:
            st.subheader("📥 Quick Reports")
            with st.container(border=True):
                st.write("Export your data:")
                if not df_hw.empty: 
                    st.download_button("⬇️ Hardware CSV", df_hw.to_csv(index=False).encode('utf-8'), "hw_report.csv", use_container_width=True)
                if not df_assets.empty: 
                    st.download_button("⬇️ Software CSV", df_assets.to_csv(index=False).encode('utf-8'), "sw_report.csv", use_container_width=True)
                if not df_logs.empty: 
                    st.download_button("⬇️ Logs CSV", df_logs.to_csv(index=False).encode('utf-8'), "logs_filtered.csv", use_container_width=True)

    elif menu == "Support":
        support_module()

    # --- SUBSCRIPTIONS (POPUP EDIT) ---
    elif menu == "Subscriptions" and role == 'admin':
        st.title("📄 Subscriptions")
        df = get_data("assets")
        tab1, tab2 = st.tabs(["View / Search / Edit", "Add & Upload"])
        
        with tab1:
            if not df.empty:
                search = st.text_input("Search Assets")
                if search:
                    df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
                
                # Checkbox selection for edit
                if "Select" not in df.columns: df.insert(0, "Select", False)
                
                # Show Data Editor (Read only mostly, but allow checkbox)
                edited = st.data_editor(df, hide_index=True, disabled=["id", "created_at", "item_name", "reference_no", "expiry_date", "category", "department", "supplier"])
                
                c_edit, c_del = st.columns([1, 4])
                
                # EDIT BUTTON (Triggers Popup)
                with c_edit:
                    if st.button("✏️ Edit Selected", key="edit_sub_btn"):
                        selected_rows = edited[edited.Select]
                        if len(selected_rows) == 1:
                            # Open Dialog with the selected row data
                            edit_asset_dialog(selected_rows.iloc[0].to_dict())
                        elif len(selected_rows) > 1:
                            st.warning("Please select exactly ONE item to edit.")
                        else:
                            st.info("Select an item to edit.")
                
                # DELETE BUTTON
                with c_del:
                    if st.button("🗑️ Delete Selected"):
                        selected = edited[edited.Select]
                        if not selected.empty:
                            confirm_delete("assets", selected['id'].tolist())
                        else: st.warning("Select items first.")
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

    # --- HARDWARE (POPUP EDIT) ---
    elif menu == "Hardware" and role == 'admin':
        st.title("💻 Hardware Management")
        tab_report, tab_inv, tab_add, tab_assign = st.tabs(["Master Report", "Inventory (Edit)", "Add & Upload", "Assign Asset"])
        
        # TAB 1: MASTER REPORT
        with tab_report:
            st.subheader("📋 Hardware Master Report")
            try:
                hw_data = supabase.table("hardware").select("*").execute().data
                staff_data = supabase.table("staff").select("*").execute().data
                if hw_data:
                    df_hw = pd.DataFrame(hw_data)
                    df_staff = pd.DataFrame(staff_data) if staff_data else pd.DataFrame()
                    if 'assigned_to_id' in df_hw.columns and not df_staff.empty:
                        merged_df = pd.merge(df_hw, df_staff, left_on='assigned_to_id', right_on='id', how='left', suffixes=('_hw', '_staff'))
                    else: merged_df = df_hw
                    
                    column_mapping = {
                        "employee_number": "Employee Number", "full_name": "Employee Name",
                        "doj": "DOJ", "department": "Department", "asset_code": "Asset Code",
                        "serial_no": "Laptop S/N", "model": "Laptop Model Number",
                        "capitalized_date": "Capitalized Date", "assigned_to_id": "assigned_to_id", "assigned_date": "assigned_date"
                    }
                    final_df = pd.DataFrame()
                    for db_col, report_col in column_mapping.items():
                        if db_col in merged_df.columns: final_df[report_col] = merged_df[db_col]
                        else: final_df[report_col] = None 
                    st.dataframe(final_df, use_container_width=True)
                    st.download_button("⬇️ Download Report", final_df.to_csv(index=False).encode('utf-8'), "Master_Asset_Report.csv", "text/csv")
                else: st.info("No hardware found.")
            except Exception as e: st.error(f"Error generating report: {e}")

        # TAB 2: INVENTORY (POPUP EDIT)
        with tab_inv:
            st.subheader("🛠️ Manage Inventory")
            df = get_data("hardware")
            if not df.empty:
                if "Select" not in df.columns: df.insert(0, "Select", False)
                # Show columns but disable editing directly
                edited_df = st.data_editor(df, hide_index=True, use_container_width=True, disabled=["id", "created_at", "item_name", "serial_no", "model", "status", "asset_code", "capitalized_date"])
                
                c_edit, c_del = st.columns([1, 4])
                
                with c_edit:
                    if st.button("✏️ Edit Selected", key="edit_hw_btn"):
                        selected = edited_df[edited_df.Select]
                        if len(selected) == 1:
                            edit_hardware_dialog(selected.iloc[0].to_dict())
                        elif len(selected) > 1: st.warning("Select only ONE item to edit.")
                        else: st.info("Select an item to edit.")
                        
                with c_del:
                    if st.button("🗑️ Delete Selected", key="del_hw"):
                        selected = edited_df[edited_df.Select]
                        if not selected.empty: confirm_delete("hardware", selected['id'].tolist())
                        else: st.warning("Please select items to delete.")
            else: st.info("No hardware found.")

        # TAB 3: ADD
        with tab_add:
            st.subheader("Manual Entry")
            with st.form("add_hw"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Item Name (e.g. Dell XPS)")
                serial = c2.text_input("Serial No (Laptop S/N)")
                model = c1.text_input("Model Number")
                asset_code = c2.text_input("Asset Code") 
                cap_date = c1.date_input("Capitalized Date")
                stat = c2.selectbox("Status", ["Available", "Assigned", "Broken"])
                if st.form_submit_button("Add Hardware"):
                    data = {"item_name": name, "serial_no": serial, "model": model, "status": stat, "asset_code": asset_code, "capitalized_date": str(cap_date)}
                    supabase.table("hardware").insert(data).execute()
                    st.success("Added!")
                    st.rerun()
            st.divider()
            st.subheader("📂 Bulk Upload")
            c_dl, c_up = st.columns([1, 2])
            with c_dl:
                sample = pd.DataFrame([{"item_name": "Dell XPS", "serial_no": "SN-001", "model": "XPS-15", "status": "Available", "asset_code": "AST-001"}])
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

        # TAB 4: ASSIGN
        with tab_assign:
            st.subheader("🔗 Assign Hardware to Staff")
            try:
                hw_res = supabase.table("hardware").select("*").eq("status", "Available").execute()
                available_hw = hw_res.data
                staff_res = supabase.table("staff").select("*").execute()
                staff_list = staff_res.data
                if not available_hw: st.warning("No 'Available' hardware found.")
                elif not staff_list: st.warning("No Staff members found.")
                else:
                    with st.form("assign_form"):
                        hw_options = {f"{h['item_name']} - {h['serial_no']}": h['id'] for h in available_hw}
                        staff_options = {f"{s['full_name']}": s['id'] for s in staff_list}
                        s_hw = st.selectbox("Select Hardware", list(hw_options.keys()))
                        s_staff = st.selectbox("Assign to Staff", list(staff_options.keys()))
                        if st.form_submit_button("Assign Asset"):
                            hw_id = hw_options[s_hw]
                            staff_id = staff_options[s_staff]
                            supabase.table("hardware").update({"status": "Assigned", "assigned_to_id": staff_id, "assigned_date": pd.Timestamp.now().isoformat()}).eq("id", hw_id).execute()
                            log_action(st.session_state['username'], "Assign Asset", f"HW {hw_id} -> Staff {staff_id}")
                            st.success(f"Assigned successfully!")
                            time.sleep(1)
                            st.rerun()
            except Exception as e: st.error(f"Error loading assignment data: {e}")

    # --- STAFF (POPUP EDIT) ---
    elif menu == "Staff" and role == 'admin':
        st.title("👥 Staff Directory")
        df = get_data("staff")
        tab1, tab2 = st.tabs(["Directory (Edit)", "Add & Upload"])
        
        with tab1:
            if not df.empty:
                if "Select" not in df.columns: df.insert(0, "Select", False)
                edited = st.data_editor(df, hide_index=True, disabled=["id", "created_at", "full_name", "email", "department", "employee_number", "doj"])
                
                c_edit, c_del = st.columns([1, 4])
                
                with c_edit:
                    if st.button("✏️ Edit Selected", key="edit_staff_btn"):
                        selected = edited[edited.Select]
                        if len(selected) == 1:
                            edit_staff_dialog(selected.iloc[0].to_dict())
                        elif len(selected) > 1: st.warning("Select only ONE item.")
                        else: st.info("Select an item.")

                with c_del:
                    if st.button("Delete Selected Staff"):
                        selected = edited[edited.Select]
                        if not selected.empty: confirm_delete("staff", selected['id'].tolist())
                        else: st.warning("Select staff to delete.")
            else:
                st.info("No staff found.")
        
        with tab2:
            with st.form("add_staff"):
                name = st.text_input("Full Name")
                email = st.text_input("Email")
                dept = st.text_input("Department")
                emp_no = st.text_input("Employee Number")
                doj = st.date_input("Date of Joining", value=None)
                if st.form_submit_button("Save"):
                    data = {"full_name": name, "email": email, "department": dept, "employee_number": emp_no}
                    if doj: data["doj"] = str(doj)
                    supabase.table("staff").insert(data).execute()
                    st.success("Saved!")
                    st.rerun()
            st.divider()
            st.subheader("📂 Bulk Upload")
            c_dl, c_up = st.columns([1, 2])
            with c_dl:
                sample = pd.DataFrame([{"full_name": "John Doe", "email": "john@example.com", "department": "IT", "employee_number": "E001"}])
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

    # --- USERS (POPUP EDIT) ---
    elif menu == "Users" and role == 'admin':
        st.title("🔐 User Management")
        df = get_data("users")
        tab1, tab2, tab3, tab4 = st.tabs(["Edit Users", "Create User", "Bulk Upload", "Reset Password"])
        
        with tab1:
            st.subheader("✏️ Edit User Roles")
            if not df.empty:
                # Add Select Column manually since we don't have it in DB
                if "Select" not in df.columns: df.insert(0, "Select", False)
                edit_view = df.drop(columns=[DB_PASS_COL], errors='ignore')
                
                # Show grid but read-only mostly
                edited_users = st.data_editor(edit_view, hide_index=True, use_container_width=True, disabled=["id", "username", "role", "created_at"])
                
                if st.button("✏️ Edit Role (Popup)"):
                    selected = edited_users[edited_users.Select]
                    if len(selected) == 1:
                        edit_user_dialog(selected.iloc[0].to_dict())
                    elif len(selected) > 1: st.warning("Select only ONE user.")
                    else: st.info("Select a user.")
            else: st.info("No users found.")
            
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
                    except Exception as e: st.error(f"Error: {e}")
        
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
                                if DB_PASS_COL != 'password': del rec['password']
                            records.append(rec)
                        supabase.table("users").insert(records).execute()
                        st.success(f"Created {len(records)} users!")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

        with tab4:
            st.subheader("🔑 Reset User Password")
            if not df.empty:
                st.info("Select a user below to force-reset their password.")
                target_user = st.selectbox("Select User", df['username'].tolist())
                new_pass = st.text_input("New Password", type="default")
                if st.button("Update Password"):
                    if update_password(target_user, new_pass):
                        st.success(f"✅ Password for '{target_user}' has been updated!")
                        time.sleep(1)
                        st.rerun()
                    else: st.error("Failed to update.")

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
