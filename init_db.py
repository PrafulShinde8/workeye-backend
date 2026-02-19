"""
Work-Eye Single Database Schema - Multi-Tenant with Company Filtering
AUTHENTICATION FLOW:
- admin_users table: Stores login credentials for company dashboard access
- members table: Stores employee tracking data only (no login credentials)
- All companies share one database, filtered by company_id
- ALL raw tracker data stored in activity_log.raw_payload
"""
import os
import sys
import psycopg

print("\n" + "="*70)
print("🔧 Work-Eye Database - Single Database Multi-Tenant")
print("="*70)

DATABASE_URL = os.environ.get('DATABASE_URL', 
    "postgresql://work_eye_db_user:DeXsKDcQNO6rpdQypAjDECEjqRXVa8hr@dpg-d52ij3ali9vc73f8tn40-a/work_eye_db")

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

try:
    conn = psycopg.connect(DATABASE_URL, sslmode='require')
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("✅ Connected successfully!")
    
    response = input("\n⚠️  Drop existing tables and recreate? (yes/no): ").strip().lower()
    
    if response == 'yes':
        print("\n🗑️  Dropping existing tables...")
        tables_to_drop = [
            'tracker_downloads', 'date_range_reports', 'punch_logs',
            'daily_work_sessions', 'screenshots', 'window_activity',
            'activity_log', 'daily_summaries', 'members', 'devices', 
            'admin_users', 'companies'
        ]
        
        for table in tables_to_drop:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                print(f"   ✅ Dropped: {table}")
            except Exception as e:
                print(f"   ⚠️  {table}: {e}")
    
    print("\n📝 Creating tables...")
    
    # TABLE 1: companies (Company organization data)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id SERIAL PRIMARY KEY,
            license_user_id VARCHAR(100) UNIQUE,
            license_id VARCHAR(100),
            company_username VARCHAR(50) UNIQUE NOT NULL,
            company_name VARCHAR(255) NOT NULL,
            company_email VARCHAR(255) UNIQUE NOT NULL,
            package_name VARCHAR(50),
            max_employees INTEGER DEFAULT 10,
            max_devices INTEGER DEFAULT 10,
            max_storage_gb INTEGER DEFAULT 10,
            license_status VARCHAR(50) DEFAULT 'active',
            subscription_start DATE,
            subscription_end DATE,
            current_employees INTEGER DEFAULT 0,
            current_devices INTEGER DEFAULT 0,
            storage_used_gb NUMERIC(10, 2) DEFAULT 0,
            features JSONB DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("   ✅ companies")
    
    # TABLE 2: admin_users (LOGIN/SIGNUP CREDENTIALS)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            email VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            role VARCHAR(50) DEFAULT 'admin',
            is_active BOOLEAN DEFAULT TRUE,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_id, email),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)
    print("   ✅ admin_users (LOGIN CREDENTIALS)")
    
    # TABLE 3: devices
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            device_id VARCHAR(255) PRIMARY KEY,
            company_id INTEGER NOT NULL,
            username VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            hostname VARCHAR(255),
            os_info VARCHAR(255),
            member_id INTEGER,
            status VARCHAR(50) DEFAULT 'offline',
            is_idle BOOLEAN DEFAULT FALSE,
            locked BOOLEAN DEFAULT FALSE,
            current_window TEXT,
            current_process VARCHAR(255),
            last_seen TIMESTAMP,
            last_activity TIMESTAMP,
            session_start TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)
    print("   ✅ devices")
    
    # TABLE 4: members (EMPLOYEE DATA ONLY - NO LOGIN)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            email VARCHAR(255) NOT NULL,
            full_name VARCHAR(255) NOT NULL,
            employee_id VARCHAR(100),
            department VARCHAR(255),
            position VARCHAR(255),
            status VARCHAR(50) DEFAULT 'active',
            is_active BOOLEAN DEFAULT TRUE,
            last_punch_in TIMESTAMP,
            last_punch_out TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_id, email),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)
    print("   ✅ members (EMPLOYEE DATA ONLY)")
    
    # TABLE 5: daily_work_sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_work_sessions (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            device_id VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            member_id INTEGER,
            session_date DATE NOT NULL,
            punch_in_time TIMESTAMP,
            punch_out_time TIMESTAMP,
            is_currently_active BOOLEAN DEFAULT FALSE,
            session_status VARCHAR(50) DEFAULT 'not_started',
            current_total_seconds NUMERIC(12, 2) DEFAULT 0,
            current_active_seconds NUMERIC(12, 2) DEFAULT 0,
            current_idle_seconds NUMERIC(12, 2) DEFAULT 0,
            current_locked_seconds NUMERIC(12, 2) DEFAULT 0,
            screen_time_hours NUMERIC(8, 4) DEFAULT 0,
            active_time_hours NUMERIC(8, 4) DEFAULT 0,
            idle_time_hours NUMERIC(8, 4) DEFAULT 0,
            locked_time_hours NUMERIC(8, 4) DEFAULT 0,
            productivity_percentage NUMERIC(5, 2) DEFAULT 0,
            last_activity_update TIMESTAMP,
            screenshots_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_id, device_id, session_date),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
            FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE SET NULL
        )
    """)
    print("   ✅ daily_work_sessions")
    
    # TABLE 6: activity_log (STORES ALL RAW DATA)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            device_id VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            username VARCHAR(255),
            member_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_start TIMESTAMP,
            last_activity TIMESTAMP,
            total_seconds NUMERIC(12, 2) DEFAULT 0,
            active_seconds NUMERIC(12, 2) DEFAULT 0,
            idle_seconds NUMERIC(12, 2) DEFAULT 0,
            locked_seconds NUMERIC(12, 2) DEFAULT 0,
            idle_for NUMERIC(10, 2) DEFAULT 0,
            current_window TEXT,
            current_process VARCHAR(255),
            is_idle BOOLEAN DEFAULT FALSE,
            locked BOOLEAN DEFAULT FALSE,
            mouse_active BOOLEAN DEFAULT FALSE,
            keyboard_active BOOLEAN DEFAULT FALSE,
            windows_opened JSONB DEFAULT '[]',
            browser_history JSONB DEFAULT '[]',
            screenshot TEXT,
            raw_payload JSONB DEFAULT '{}',
            daily_session_id INTEGER,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
            FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE SET NULL,
            FOREIGN KEY (daily_session_id) REFERENCES daily_work_sessions(id) ON DELETE CASCADE
        )
    """)
    print("   ✅ activity_log (ALL RAW DATA)")
    
    # TABLE 7: screenshots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            device_id VARCHAR(255) NOT NULL,
            member_id INTEGER,
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            window_title TEXT,
            process_name VARCHAR(255),
            is_idle BOOLEAN DEFAULT FALSE,
            screenshot_data TEXT NOT NULL,
            daily_session_id INTEGER,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
            FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE SET NULL,
            FOREIGN KEY (daily_session_id) REFERENCES daily_work_sessions(id) ON DELETE CASCADE
        )
    """)
    print("   ✅ screenshots")
    
    # TABLE 8: window_activity
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS window_activity (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            device_id VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            window_title TEXT,
            process_name VARCHAR(255),
            total_time_seconds NUMERIC(12, 2) DEFAULT 0,
            visit_count INTEGER DEFAULT 1,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            UNIQUE(company_id, device_id, date, window_title, process_name),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
        )
    """)
    print("   ✅ window_activity")
    
    # TABLE 9: daily_summaries
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            device_id VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            username VARCHAR(255),
            total_screen_time NUMERIC(8, 2) DEFAULT 0,
            active_time NUMERIC(8, 2) DEFAULT 0,
            idle_time NUMERIC(8, 2) DEFAULT 0,
            locked_time NUMERIC(8, 2) DEFAULT 0,
            productivity_percentage NUMERIC(5, 2) DEFAULT 0,
            screenshots_captured INTEGER DEFAULT 0,
            first_activity TIMESTAMP,
            last_activity TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_id, device_id, date),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
        )
    """)
    print("   ✅ daily_summaries")
    
    # TABLE 10: punch_logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS punch_logs (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            email VARCHAR(255) NOT NULL,
            action VARCHAR(20) NOT NULL,
            device_id VARCHAR(255),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_minutes INTEGER,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
        )
    """)
    print("   ✅ punch_logs")
    
    # TABLE 11: tracker_downloads
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracker_downloads (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            company_username VARCHAR(50) NOT NULL,
            download_token VARCHAR(255) UNIQUE NOT NULL,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            downloaded_by VARCHAR(255),
            backend_url TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)
    print("   ✅ tracker_downloads")
    
    # TABLE 12: date_range_reports
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS date_range_reports (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            device_id VARCHAR(255),
            report_type VARCHAR(50),
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            report_data JSONB NOT NULL,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)
    print("   ✅ date_range_reports")
    
    print("\n🚀 Creating indexes...")
    
    indexes = [
        ("idx_companies_username", "companies(company_username)"),
        ("idx_admin_users_company", "admin_users(company_id, is_active)"),
        ("idx_admin_users_email", "admin_users(email)"),
        ("idx_devices_company", "devices(company_id, status)"),
        ("idx_members_company", "members(company_id, is_active)"),
        ("idx_sessions_company_date", "daily_work_sessions(company_id, session_date DESC)"),
        ("idx_activity_company_time", "activity_log(company_id, timestamp DESC)"),
        ("idx_screenshots_company", "screenshots(company_id, captured_at DESC)"),
    ]
    
    for idx_name, idx_def in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}")
        except Exception as e:
            print(f"   ⚠️  Index {idx_name}: {e}")
    
    print(f"   ✅ Created {len(indexes)} indexes")
    
    try:
        cursor.execute("ALTER TABLE devices ADD CONSTRAINT fk_devices_members FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE SET NULL")
    except:
        pass
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*70)
    print("✅ DATABASE READY!")
    print("="*70)
    print("\n📊 Single database for ALL companies")
    print("🔑 Login/Signup: admin_users table")
    print("👥 Employee tracking: members table")
    print("🔗 Dashboard: frontend-8x7e.onrender.com/login")
    print("📡 Tracker: backend-35m2.onrender.com/{username}/upload-activity")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
