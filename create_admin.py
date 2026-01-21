# create_admin.py
import streamlit as st
from auth import create_user

# Setup the first admin user
username = "admin"
password = "password123"  # You can change this later
role = "admin"

print(f"Creating user: {username}...")

if create_user(username, password, role):
    print("✅ SUCCESS: Admin user created!")
    print(f"👉 Login with Username: {username} | Password: {password}")
else:
    print("❌ ERROR: User might already exist or DB connection failed.")