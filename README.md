Here is the updated README.md for your project, rewritten to reflect the move from Desktop/Tkinter to Web/Streamlit. I have included the live demo link prominently at the top as requested.

# IMS - Web Asset Management System

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://webappsams.streamlit.app/)

A secure, role-based Inventory & Asset Management System (IMS) built with Python and Streamlit. This web application enables real-time tracking of hardware assets, software subscriptions, and staff assignments using a centralized PostgreSQL database.

🔗 Live Demo: [https://webappsams.streamlit.app/](https://webappsams.streamlit.app/)

---

 🚀 Features

# 📊 Interactive Dashboard
* Real-Time Overview: Instant metrics on total subscriptions, expiring licenses, and hardware availability.
* Global Search: A powerful search bar to find assets, serial numbers, or staff members across the entire system.
* Visual Analytics: Charts showing "Assets by Department" and "Hardware Status" distributions.
* Smart Alerts: Auto-generated warnings for items expiring within the next 30 days.

# 💻 Hardware & Asset Management
* Inventory Tracking: Add, edit, and delete hardware (Laptops, Peripherals, etc.) with serial number tracking.
* Staff Assignment: Assign devices directly to staff members; the system tracks who has what and when it was assigned.
* Lifecycle Management: Mark items as *Available*, *Assigned*, *Maintenance*, or *Broken*.

# 🔐 Security & User Administration
* Role-Based Access Control (RBAC):
    * Admin: Full control (Manage Users, Delete Records, Reset Passwords).
    * User/Manager: Restricted access to standard operational features.
* Secure Authentication: Passwords are hashed and salted (SHA-256 + PBKDF2) before storage.
* User Management: Admins can create new users, update roles, and reset passwords directly from the UI.

# 🧾 Reporting & Audits
* Exportable Reports: Generate and download CSV reports for:
    * Hardware assigned in a specific date range.
    * Software expiring soon.
    * Full system audit logs.
* Audit Logging: Critical actions (Logins, Asset Creation, Deletions) are logged with timestamps and user IDs.
* Support Portal: Built-in form for users to submit issues or reports to administrators.

---

 🛠️ Tech Stack

* Frontend: [Streamlit](https://streamlit.io/) (Python-based Web UI)
* Database: PostgreSQL (Hosted on Supabase)
* Backend Logic: Python 3.10+
* Data Processing: Pandas
* Database Adapter: Psycopg2-binary

---

 📂 Project Structure

```text
webapp_sams/
│
├── app.py                 # Main Application (UI, Routing, & Dashboard)
├── database.py            # Database Connection & CRUD Operations
├── auth.py                # Authentication, Password Hashing & User Logic
├── logs.py                # Audit Logging System
├── requirements.txt       # Python Dependencies
└── README.md              # Documentation
⚙️ Installation & Setup

1. Clone the Repository
git clone <repository-url>
cd webapp_sams
2. Install Dependencies
pip install -r requirements.txt
3. Database Configuration
This app connects to a PostgreSQL database. Ensure you have the following tables set up in your database (e.g., Supabase, local Postgres):

Click to view SQL Schema
4. Run the Application
streamlit run app.py


👨‍💻 Credits

Designed and Developed by Harsh Joshi