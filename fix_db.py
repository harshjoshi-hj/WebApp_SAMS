import streamlit as st
import psycopg2

def fix_database():
    st.title("🛠️ Database Fixer")
    
    if st.button("Run Fix (Add Missing Columns)"):
        try:
            # Connect using your existing secrets
            db_config = st.secrets["connections"]["postgresql"]
            conn = psycopg2.connect(
                host=db_config["host"],
                user=db_config["username"],
                password=db_config["password"],
                port=db_config["port"],
                dbname=db_config["database"],
                sslmode='require'
            )
            cur = conn.cursor()
            
            # 1. Add 'ip_address' column if it doesn't exist
            st.write("Adding 'ip_address' column...")
            cur.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS ip_address TEXT;")
            
            # 2. Add 'details' column if it doesn't exist
            st.write("Adding 'details' column...")
            cur.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS details TEXT;")
            
            conn.commit()
            cur.close()
            conn.close()
            
            st.success("✅ Success! Database columns added. You can now delete this file and restart your main app.")
            
        except Exception as e:
            st.error(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_database()