import streamlit as st
import pandas as pd
import time
from auth import login_user, create_user, change_user_password
from logs import log_action
from database import (
    connect, get_dashboard_stats, get_department_counts, get_hardware_status_counts, 
    get_all_staff, delete_staff, add_hardware, delete_hardware, update_hardware_status, 
    get_all_users, delete_user, update_user_role, add_asset, add_staff_member,
    delete_asset, update_asset
)

# 1. Page Config (MUST BE FIRST)
st.set_page_config(page_title="LS Cable - IMS", page_icon="📦", layout="wide")

# --- ⏳ SESSION TIMEOUT LOGIC ---
TIMEOUT_MINS = 30 
if 'last_active' not in st.session_state:
    st.session_state['last_active'] = time.time()

if 'logged_in' in st.session_state and st.session_state['logged_in']:
    if time.time() - st.session_state['last_active'] > (TIMEOUT_MINS * 60):
        if 'username' in st.session_state:
            log_action(st.session_state['username'], "Session Timeout", "Auto Logout")
        st.session_state.clear()
        st.rerun()
    else:
        st.session_state['last_active'] = time.time()

# 2. Session State Setup
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'role' not in st.session_state:
    st.session_state['role'] = ""

# --- HELPER: CONFIRMATION DIALOG ---
@st.dialog("⚠️ Confirm Bulk Deletion")
def confirm_delete_dialog(item_type, ids_to_delete, delete_func):
    st.write(f"You are about to delete **{len(ids_to_delete)}** {item_type}(s).")
    st.error("This action cannot be undone.")
    st.write("Please type **DELETE** below to confirm:")
    confirm_input = st.text_input("Confirmation", placeholder="Type DELETE here")
    if st.button("Confirm Delete", type="primary"):
        if confirm_input == "DELETE":
            success_count = 0
            for item_id in ids_to_delete:
                if delete_func(item_id): success_count += 1
            st.success(f"Deleted {success_count} items.")
            log_action(st.session_state['username'], "Bulk Delete", f"{item_type}: {success_count}")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Type 'DELETE' to confirm.")

# --- LOGIN PAGE ---
def login_page():
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.title("📦 LS Cable IMS")
        st.subheader("System Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            role = login_user(username, password)
            if role:
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.session_state['role'] = role
                st.session_state['last_active'] = time.time()
                log_action(username, "Login", "Web Access")
                st.rerun()
            else:
                st.error("Invalid Username or Password")

# --- DASHBOARD PAGE ---
def main_app():
    st.sidebar.title(f"👤 {st.session_state['username']}")
    st.sidebar.caption(f"Role: {st.session_state['role']}")
    
    # Define Permissions
    is_privileged = st.session_state['role'] in ['admin', 'manager']
    is_admin = st.session_state['role'] == 'admin'
    
    if is_privileged:
        menu_options = [
            "Dashboard", "All Subscriptions", "Add Subscription", 
            "Staff Directory", "Hardware Assets", "User Management", 
            "Audit Logs", "Support / Reports"
        ]
    else:
        menu_options = [
            "Dashboard", "All Subscriptions", "Add Subscription", 
            "Hardware Assets", "Support / Reports"
        ]
    
    menu = st.sidebar.radio("Main Menu", menu_options)
    
    if st.sidebar.button("Logout", type="primary"):
        if 'username' in st.session_state:
            log_action(st.session_state['username'], "Logout", "Web Access")
        st.session_state.clear()
        st.rerun()

    # --- 1. DASHBOARD ---
    if menu == "Dashboard":
        st.title("📊 System Overview")
        
        search_term = st.text_input("🔍 Global Search", placeholder="Search assets, serial numbers...")
        if search_term:
            st.subheader(f"Results for: '{search_term}'")
            conn = connect()
            if conn:
                df_hw = pd.read_sql(f"SELECT * FROM hardware WHERE item_name ILIKE '%%{search_term}%%' OR serial_no ILIKE '%%{search_term}%%'", conn)
                if not df_hw.empty:
                    st.write("💻 **Hardware Found:**")
                    st.dataframe(df_hw, use_container_width=True)
                
                df_sw = pd.read_sql(f"SELECT * FROM assets WHERE item_name ILIKE '%%{search_term}%%' OR reference_no ILIKE '%%{search_term}%%'", conn)
                if not df_sw.empty:
                    st.write("📄 **Software/Assets Found:**")
                    st.dataframe(df_sw, use_container_width=True)
                conn.close()
            st.markdown("---") 

        stats = get_dashboard_stats()
        with st.container():
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📦 Subscriptions", stats.get('sub_total', 0))
            c2.metric("⚠️ Expiring Soon", stats.get('sub_expired', 0))
            c3.metric("💻 Hardware", stats.get('hw_total', 0))
            c4.metric("👤 Assigned", stats.get('hw_assigned', 0))
        
        st.divider()

        c_left, c_right = st.columns([2, 1])
        with c_left:
            st.subheader("📈 Assets by Department")
            dept_data = get_department_counts()
            if dept_data: st.bar_chart(dept_data, color="#3498db")
        with c_right:
            st.subheader("💻 Status")
            hw_data = get_hardware_status_counts()
            if hw_data: st.dataframe(pd.DataFrame(list(hw_data.items()), columns=["Status", "Count"]), use_container_width=True, hide_index=True)

        st.divider()

        st.subheader("📥 Generate Reports")
        with st.container():
            d_col1, d_col2 = st.columns(2)
            start_date = d_col1.date_input("Start Date", value=pd.to_datetime("today") - pd.Timedelta(days=30))
            end_date = d_col2.date_input("End Date", value=pd.to_datetime("today"))

        st.divider()
        c_rep1, c_rep2, c_rep3 = st.columns(3)
        conn = connect()
        if conn:
            with c_rep1:
                st.info("💻 Hardware Assigned")
                query_hw = f"SELECT * FROM hardware WHERE assigned_date BETWEEN '{start_date}' AND '{end_date}'"
                df_hw = pd.read_sql(query_hw, conn)
                if not df_hw.empty:
                    st.download_button("⬇️ CSV", df_hw.to_csv(index=False).encode('utf-8'), f"hw_{start_date}.csv")

            with c_rep2:
                st.info("📄 Software Expiring")
                query_sw = f"SELECT * FROM assets WHERE expiry_date BETWEEN '{start_date}' AND '{end_date}'"
                df_sw = pd.read_sql(query_sw, conn)
                if not df_sw.empty:
                    st.download_button("⬇️ CSV", df_sw.to_csv(index=False).encode('utf-8'), f"sw_{start_date}.csv")

            if is_privileged:
                with c_rep3:
                    st.info("📜 Audit Logs")
                    query_logs = f"SELECT * FROM logs WHERE timestamp >= '{start_date}' AND timestamp <= '{end_date} 23:59:59'"
                    df_logs = pd.read_sql(query_logs, conn)
                    if not df_logs.empty:
                        st.download_button("⬇️ CSV", df_logs.to_csv(index=False).encode('utf-8'), f"logs_{start_date}.csv")
            conn.close()

        st.divider()
        if is_privileged:
            c_logs, c_alerts = st.columns(2)
            with c_logs:
                st.subheader("🕒 Recent Activity")
                conn = connect()
                if conn:
                    recent_logs = pd.read_sql("SELECT user, action, target, timestamp FROM logs ORDER BY timestamp DESC LIMIT 5", conn)
                    st.dataframe(recent_logs, use_container_width=True, hide_index=True)
                    conn.close()
            with c_alerts:
                display_alerts()
        else:
            display_alerts()

    # --- 2. ALL SUBSCRIPTIONS ---
    elif menu == "All Subscriptions":
        st.title("📄 Subscription Management")
        
        is_admin = st.session_state['role'] == 'admin'
        conn = connect()
        if conn:
            query_expiring = "SELECT * FROM assets WHERE expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days' ORDER BY expiry_date ASC"
            df_expiring = pd.read_sql(query_expiring, conn)
            
            if not df_expiring.empty:
                st.error(f"🚨 Action Required: {len(df_expiring)} items are expiring this month!")
                st.dataframe(df_expiring, use_container_width=True)
            else:
                st.success("✅ No items expiring in the next 30 days.")
            
            st.divider()

            if is_admin:
                tab1, tab2, tab3 = st.tabs(["📋 View All", "✏️ Manage (Edit)", "🗑 Delete (Admin Only)"])
            else:
                tab1, tab2 = st.tabs(["📋 View All", "✏️ Manage (Edit)"])

            with tab1:
                df_all = pd.read_sql("SELECT * FROM assets ORDER BY expiry_date DESC", conn)
                st.dataframe(df_all, use_container_width=True)

            with tab2:
                st.subheader("Update Subscription Details")
                df_assets = pd.read_sql("SELECT id, item_name, reference_no FROM assets", conn)
                
                if not df_assets.empty:
                    asset_opts = {f"{row['id']} - {row['item_name']}": row['id'] for i, row in df_assets.iterrows()}
                    selected_label = st.selectbox("Select Asset to Update", list(asset_opts.keys()))
                    selected_id = asset_opts[selected_label]
                    
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM assets WHERE id = %s", (selected_id,))
                    record = cur.fetchone()
                    
                    if record:
                        with st.form("edit_asset_form"):
                            c1, c2 = st.columns(2)
                            new_item = c1.text_input("Item Name", value=record[1])
                            new_ref = c2.text_input("Reference No", value=record[2])
                            new_expiry = c1.date_input("Expiry Date", value=record[3])
                            
                            cats = ["Software", "License", "Domain"]
                            cat_idx = cats.index(record[4]) if record[4] in cats else 0
                            new_cat = c2.selectbox("Category", cats, index=cat_idx)
                            
                            depts = ["IT", "HR", "Finance", "Sales"]
                            dept_idx = depts.index(record[5]) if record[5] in depts else 0
                            new_dept = c1.selectbox("Department", depts, index=dept_idx)
                            
                            new_supp = c2.text_input("Supplier", value=record[6])
                            
                            if st.form_submit_button("💾 Save Changes"):
                                changes = []
                                old_summary = []
                                
                                if record[1] != new_item: 
                                    changes.append(f"Name: {new_item}")
                                    old_summary.append(f"Name: {record[1]}")
                                    
                                if str(record[3]) != str(new_expiry): 
                                    changes.append(f"Expiry: {new_expiry}")
                                    old_summary.append(f"Expiry: {record[3]}")
                                    
                                if record[5] != new_dept:
                                    changes.append(f"Dept: {new_dept}")
                                    old_summary.append(f"Dept: {record[5]}")

                                if update_asset(selected_id, new_item, new_ref, new_expiry, new_cat, new_dept, new_supp):
                                    st.success("Asset updated!")
                                    
                                    if changes:
                                        log_action(
                                            user=st.session_state['username'], 
                                            action="Update Asset", 
                                            target=f"{new_item} (ID: {selected_id})",
                                            old_value=", ".join(old_summary),
                                            new_value=", ".join(changes)
                                        )
                                    else:
                                        log_action(st.session_state['username'], "Update Asset", new_item)
                                        
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Update failed.")
                else:
                    st.info("No assets to edit.")

            if is_admin:
                with tab3:
                    st.subheader("🗑 Bulk Delete Subscriptions")
                    df_del = pd.read_sql("SELECT id, item_name, expiry_date, department FROM assets", conn)
                    if not df_del.empty:
                        df_del.insert(0, "Select", False)
                        edited_del = st.data_editor(
                            df_del, 
                            hide_index=True, 
                            column_config={"Select": st.column_config.CheckboxColumn(required=True)},
                            disabled=["id", "item_name", "expiry_date", "department"]
                        )
                        selected_rows = edited_del[edited_del.Select]
                        if not selected_rows.empty:
                            if st.button("🗑 Delete Selected Assets", type="primary"):
                                confirm_delete_dialog("Subscription", selected_rows['id'].tolist(), delete_asset)
                    else:
                        st.info("No assets found.")
            conn.close()

    # --- 3. ADD SUBSCRIPTION ---
    elif menu == "Add Subscription":
        st.title("➕ Add New Subscription")
        
        with st.expander("📂 Bulk Upload Subscriptions (CSV)"):
            c_dl, c_up = st.columns([1, 2])
            with c_dl:
                st.write("Download Template:")
                sample_sub = pd.DataFrame([{"item_name": "Office 365", "reference_no": "MS-101", "expiry_date": "2026-12-31", "category": "Software", "department": "IT", "supplier": "Microsoft"}])
                st.download_button("📄 Template CSV", sample_sub.to_csv(index=False).encode('utf-8'), "subscriptions_template.csv")
            
            with c_up:
                sub_file = st.file_uploader("Upload CSV", key="sub_up")
            
            if sub_file and st.button("🚀 Process Bulk Subscriptions"):
                try:
                    data = pd.read_csv(sub_file)
                    success_count = 0
                    for _, row in data.iterrows():
                        if add_asset(
                            str(row['item_name']), 
                            str(row['reference_no']), 
                            row['expiry_date'], 
                            str(row['category']), 
                            str(row['department']), 
                            str(row['supplier'])
                        ):
                            success_count += 1
                    
                    st.success(f"Successfully added {success_count} subscriptions!")
                    log_action(st.session_state['username'], "Bulk Add", f"Subscriptions: {success_count}")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing CSV: {e}")

        st.divider()

        with st.form("add_sub"):
            st.subheader("Manual Entry")
            c1, c2 = st.columns(2)
            item = c1.text_input("Item Name")
            ref = c2.text_input("Reference No")
            expiry = c1.date_input("Expiry Date")
            cat = c2.selectbox("Category", ["Software", "License", "Domain"])
            dept = c1.selectbox("Department", ["IT", "HR", "Finance", "Sales"])
            supp = c2.text_input("Supplier")
            if st.form_submit_button("Save Asset"):
                if add_asset(item, ref, expiry, cat, dept, supp):
                    st.success("Asset Added!")
                    log_action(st.session_state['username'], "Add Asset", item)

    # --- 4. STAFF DIRECTORY (UPDATED) ---
    elif menu == "Staff Directory":
        if not is_privileged:
            st.error("⛔ Access Denied")
        else:
            st.title("👥 Staff Directory")
            tab1, tab2, tab3 = st.tabs(["View Staff", "Add New", "Delete"])
            
            with tab1:
                conn = connect()
                if conn:
                    st.dataframe(pd.read_sql("SELECT * FROM staff", conn), use_container_width=True)
                    conn.close()
            
            # TAB 2: ADD STAFF (With Template)
            with tab2:
                st.subheader("Add Staff")
                
                with st.expander("📂 Bulk Upload Staff (CSV)"):
                    c_dl, c_up = st.columns([1, 2])
                    
                    with c_dl:
                        st.write("Download Template:")
                        sample_staff = pd.DataFrame([{"full_name": "Alice Smith", "username": "asmith", "email": "alice@company.com", "phone": "555-0101", "gender": "Female", "dob": "1990-01-01"}])
                        st.download_button("📄 Template CSV", sample_staff.to_csv(index=False).encode('utf-8'), "staff_template.csv")
                    
                    with c_up:
                        u_file = st.file_uploader("Upload CSV", key="staff_up")
                    
                    if u_file and st.button("🚀 Process Bulk Staff"):
                        try:
                            data = pd.read_csv(u_file)
                            success_count = 0
                            for _, row in data.iterrows():
                                 if add_staff_member(str(row['full_name']), str(row['username']), str(row.get('email','')), str(row.get('phone','')), str(row.get('gender','')), row.get('dob'), st.session_state['username']):
                                     success_count += 1
                            st.success(f"Successfully uploaded {success_count} staff members!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error processing CSV: {e}")

                st.divider()
                
                with st.form("add_staff"):
                    c1, c2 = st.columns(2)
                    name = c1.text_input("Name")
                    u_name = c2.text_input("Username")
                    email = c1.text_input("Email")
                    phone = c2.text_input("Phone")
                    gender = c1.selectbox("Gender", ["Male", "Female", "Other"])
                    dob = c2.date_input("DOB")
                    if st.form_submit_button("Add"):
                        add_staff_member(name, u_name, email, phone, gender, dob, st.session_state['username'])
                        st.success("Added!")
                        st.rerun()

            with tab3:
                st.subheader("Delete Staff")
                conn = connect()
                if conn:
                    df = pd.read_sql("SELECT id, full_name FROM staff", conn)
                    conn.close()
                    if not df.empty:
                        df.insert(0, "Select", False)
                        edited = st.data_editor(df, hide_index=True)
                        if st.button("Delete Selected"):
                            selected = edited[edited.Select]
                            if not selected.empty:
                                confirm_delete_dialog("Staff", selected['id'].tolist(), delete_staff)

    # --- 5. HARDWARE ASSETS ---
    elif menu == "Hardware Assets":
        st.title("💻 Hardware Assets")
        tab1, tab2, tab3 = st.tabs(["View Inventory", "Add New", "Delete"])
        
        with tab1:
            conn = connect()
            if conn:
                st.dataframe(pd.read_sql("SELECT h.id, h.item_name, h.serial_no, h.status, s.username FROM hardware h LEFT JOIN staff s ON h.assigned_to_id = s.id ORDER BY h.id ASC", conn), use_container_width=True)
                conn.close()

        with tab2:
            st.subheader("Add Hardware")
            
            with st.expander("📂 Bulk Upload Hardware (CSV)"):
                c_dl, c_up = st.columns([1, 2])
                with c_dl:
                    st.write("Download Template:")
                    sample_hw = pd.DataFrame([{"item_name": "Dell XPS 15", "serial_no": "SN998877", "model": "XPS-9500", "status": "Available"}])
                    st.download_button("📄 Template CSV", sample_hw.to_csv(index=False).encode('utf-8'), "hardware_template.csv")
                
                with c_up:
                    u_file = st.file_uploader("Upload CSV", key="hw_up")
                
                if u_file and st.button("🚀 Process Bulk Hardware"):
                    try:
                        data = pd.read_csv(u_file)
                        success_count = 0
                        for _, row in data.iterrows():
                            if add_hardware(str(row['item_name']), str(row['serial_no']), str(row['model']), str(row['status'])):
                                success_count += 1
                        st.success(f"Successfully added {success_count} hardware items!")
                        log_action(st.session_state['username'], "Bulk Add", f"Hardware: {success_count}")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error processing CSV: {e}")
            
            st.divider()
            
            with st.form("add_hw"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Item")
                serial = c2.text_input("Serial")
                model = c1.text_input("Model")
                status = c2.selectbox("Status", ["Available", "Assigned", "Maintenance", "Broken"])
                if st.form_submit_button("Save"):
                    add_hardware(name, serial, model, status)
                    st.success("Saved!")
                    st.rerun()

        with tab3:
            st.subheader("Delete Hardware")
            conn = connect()
            if conn:
                df = pd.read_sql("SELECT id, item_name, serial_no FROM hardware", conn)
                conn.close()
                if not df.empty:
                    df.insert(0, "Select", False)
                    edited = st.data_editor(df, hide_index=True)
                    if st.button("Delete Selected"):
                        selected = edited[edited.Select]
                        if not selected.empty:
                             confirm_delete_dialog("Hardware", selected['id'].tolist(), delete_hardware)

    # --- 6. USER MANAGEMENT ---
    elif menu == "User Management":
        if not is_admin:
            st.error("⛔ Access Denied")
        else:
            st.title("🔐 User Management")
            tab1, tab2, tab3 = st.tabs(["View Users", "Create User", "Manage"])
            
            with tab1:
                conn = connect()
                if conn:
                    st.dataframe(pd.read_sql("SELECT id, username, role FROM users ORDER BY id ASC", conn), use_container_width=True)
                    conn.close()
            
            with tab2:
                st.subheader("Create System User")
                with st.expander("📂 Bulk Upload Users (CSV)"):
                    c_dl, c_up = st.columns([1, 2])
                    with c_dl:
                        st.write("Download Template:")
                        sample = pd.DataFrame([{"username": "jdoe", "password": "password123", "role": "user"}])
                        st.download_button("📄 Template CSV", sample.to_csv(index=False).encode('utf-8'), "users_template.csv")
                    
                    with c_up:
                        u_file = st.file_uploader("Upload CSV", key="user_up")
                    
                    if u_file and st.button("🚀 Process Bulk Users"):
                        try:
                            data = pd.read_csv(u_file)
                            success_count = 0
                            for _, row in data.iterrows():
                                if create_user(str(row['username']), str(row['password']), str(row['role'])):
                                    success_count += 1
                            st.success(f"Successfully created {success_count} users!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error processing CSV: {e}")

                st.divider()
                
                with st.form("create_user"):
                    new_u = st.text_input("Username")
                    new_p = st.text_input("Password", type="password")
                    new_r = st.selectbox("Role", ["admin", "manager", "user"])
                    if st.form_submit_button("Create"):
                        if create_user(new_u, new_p, new_r):
                            st.success("User Created!")
                            st.rerun()
            
            with tab3:
                st.subheader("Manage Users")
                
                conn = connect()
                if conn:
                    df = pd.read_sql("SELECT id, username, role FROM users ORDER BY id ASC", conn)
                    conn.close()
                    
                    st.write("### ✏️ Edit User Details")
                    user_opts = {f"{row['username']}": row['id'] for i, row in df.iterrows()}
                    sel_u = st.selectbox("Select User to Edit", list(user_opts.keys()))
                    sel_id = user_opts[sel_u]
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        new_role = st.selectbox("New Role", ["admin", "user", "manager"])
                        if st.button("Update Role"):
                            update_user_role(sel_id, new_role)
                            st.success("Role Updated")
                            st.rerun()
                    
                    st.divider()
                    
                    st.write("### 🗑 Bulk Delete Users")
                    if not df.empty:
                        df.insert(0, "Select", False)
                        edited_users = st.data_editor(
                            df, 
                            hide_index=True, 
                            column_config={"Select": st.column_config.CheckboxColumn(required=True)},
                            disabled=["id", "username", "role"]
                        )
                        
                        selected_users = edited_users[edited_users.Select]
                        
                        if not selected_users.empty:
                            if st.session_state['username'] in selected_users['username'].values:
                                st.error("❌ Safety Lock: You cannot delete your own account!")
                            else:
                                st.warning(f"⚠️ {len(selected_users)} users selected.")
                                if st.button("🗑 Delete Selected Users", type="primary"):
                                    confirm_delete_dialog("System User", selected_users['id'].tolist(), delete_user)

    # --- 7. AUDIT LOGS (PRIVILEGED ONLY) ---
    elif menu == "Audit Logs":
        if not is_privileged:
            st.error("⛔ Access Denied")
        else:
            st.title("📜 Audit Logs")
            conn = connect()
            if conn:
                st.dataframe(pd.read_sql("SELECT * FROM logs ORDER BY timestamp DESC", conn), use_container_width=True)
                conn.close()

    # --- 8. REPORTS ---
    elif menu == "Support / Reports":
        st.title("📢 Support")
        
        if not is_admin:
            st.subheader("Submit Report")
            with st.form("rep"):
                subj = st.text_input("Subject")
                msg = st.text_area("Message")
                if st.form_submit_button("Submit"):
                    conn = connect()
                    if conn:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO reports (username, subject, message) VALUES (%s, %s, %s)", 
                                   (st.session_state['username'], subj, msg))
                        conn.commit()
                        conn.close()
                        st.success("Submitted!")

        if is_privileged:
            st.subheader("Incoming Reports")
            conn = connect()
            if conn:
                st.dataframe(pd.read_sql("SELECT * FROM reports ORDER BY timestamp DESC", conn), use_container_width=True)
                conn.close()

def display_alerts():
    st.subheader("🚨 Expiring Soon (Next 30 Days)")
    conn = connect()
    if conn:
        query = "SELECT item_name, expiry_date, department FROM assets WHERE expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'"
        expiring = pd.read_sql(query, conn)
        if not expiring.empty:
            st.error(f"⚠️ {len(expiring)} items need attention!")
            st.dataframe(expiring, use_container_width=True)
        else:
            st.success("✅ No items expiring soon.")
        conn.close()

# --- APP START ---
if st.session_state['logged_in']:
    main_app()
else:
    login_page()