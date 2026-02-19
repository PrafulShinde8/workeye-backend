#!/usr/bin/env python3
"""
QUICK_SETUP_DB.PY - Fast Database Initialization
================================================
Run this ONCE to create all tables in the external database
"""

import psycopg2
from psycopg2.extras import RealDictCursor

# Your external database URL
DATABASE_URL = 'postgresql://work_eye_db_user:DeXsKDcQNO6rpdQypAjDECEjqRXVa8hr@dpg-d52ij3ali9vc73f8tn40-a.singapore-postgres.render.com/work_eye_db'

def setup_database():
    """Create all necessary tables"""
    print("\n🚀 Starting database setup...\n")
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require')
    cur = conn.cursor()
    
    try:
        # 1. Create companies table
        print("📊 Creating companies table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id SERIAL PRIMARY KEY,
                company_username VARCHAR(100) UNIQUE NOT NULL,
                company_name VARCHAR(255) NOT NULL,
                tracker_token TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Companies table ready")
        
        # 2. Create users table (for admin authentication)
        print("👥 Creating users table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name VARCHAR(255),
                role VARCHAR(50) DEFAULT 'admin',
                is_active BOOLEAN DEFAULT TRUE,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Users table ready")
        
        # 3. Create members table (for employees)
        print("👤 Creating members table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                username VARCHAR(100) NOT NULL,
                email VARCHAR(255),
                full_name VARCHAR(255),
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, username)
            )
        """)
        print("   ✅ Members table ready")
        
        # 4. Create devices table
        print("💻 Creating devices table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                member_id INTEGER REFERENCES members(id) ON DELETE CASCADE,
                device_id VARCHAR(255) UNIQUE NOT NULL,
                device_name VARCHAR(255),
                os_type VARCHAR(50),
                last_seen TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Devices table ready")
        
        # 5. Create screenshots table
        print("📸 Creating screenshots table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS screenshots (
                id SERIAL PRIMARY KEY,
                device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE,
                screenshot_url TEXT,
                timestamp TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Screenshots table ready")
        
        # 6. Create activity_logs table
        print("📝 Creating activity_logs table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id SERIAL PRIMARY KEY,
                device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE,
                activity_type VARCHAR(100),
                activity_data JSONB,
                timestamp TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Activity logs table ready")
        
        # 7. Create attendance table
        print("🕒 Creating attendance table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                member_id INTEGER REFERENCES members(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                check_in TIMESTAMP,
                check_out TIMESTAMP,
                total_hours DECIMAL(5,2),
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(member_id, date)
            )
        """)
        print("   ✅ Attendance table ready")
        
        # 8. Create website_visits table
        print("🌐 Creating website_visits table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS website_visits (
                id SERIAL PRIMARY KEY,
                device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE,
                url TEXT NOT NULL,
                title TEXT,
                visit_time TIMESTAMP NOT NULL,
                duration INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Website visits table ready")
        
        # 9. Create application_usage table
        print("📱 Creating application_usage table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS application_usage (
                id SERIAL PRIMARY KEY,
                device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE,
                app_name VARCHAR(255) NOT NULL,
                window_title TEXT,
                start_time TIMESTAMP NOT NULL,
                duration INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Application usage table ready")
        
        # Commit all changes
        conn.commit()
        
        # Verify tables
        print("\n🔍 Verifying database...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row['table_name'] for row in cur.fetchall()]
        print(f"   ✅ Found {len(tables)} tables: {', '.join(tables)}")
        
        print("\n✅ DATABASE SETUP COMPLETE!\n")
        print("You can now:")
        print("1. Sign up for a new account")
        print("2. Login with your credentials\n")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    setup_database()
