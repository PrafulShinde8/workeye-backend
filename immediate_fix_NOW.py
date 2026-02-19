"""
IMMEDIATE FIX - Reset Stuck Members (Using App DB)
====================================
Quick script to reset the 4 members currently stuck in punched-in state

This version uses your app's database connection from db.py
"""

import sys
import os
from datetime import datetime, timedelta

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import your app's database connection
from db import get_db

def immediate_fix():
    """Reset all stuck members in company 12"""
    
    print("="*70)
    print("🔧 IMMEDIATE FIX - Resetting Stuck Members")
    print("="*70)
    
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get the stuck members from company 12
            cur.execute("""
                SELECT 
                    id, 
                    name, 
                    email,
                    last_punch_in_at,
                    is_punched_in
                FROM members
                WHERE company_id = 12
                  AND is_punched_in = TRUE
                ORDER BY id
            """)
            
            members = cur.fetchall()
            
            print(f"\n📊 Found {len(members)} members to fix:\n")
            
            if len(members) == 0:
                print("✅ No stuck members found! Everything looks good.")
                return
            
            for member in members:
                member_id = member['id']
                name = member['name']
                email = member['email']
                last_punch_in = member['last_punch_in_at']
                is_punched_in = member['is_punched_in']
                
                print(f"👤 {name} ({email})")
                print(f"   Member ID: {member_id}")
                print(f"   Last Punch In: {last_punch_in}")
                print(f"   Currently Punched In: {is_punched_in}")
                
                # Check if there's already a punch-out after last punch-in
                cur.execute("""
                    SELECT id, timestamp, action
                    FROM punch_logs
                    WHERE member_id = %s
                      AND timestamp > %s
                      AND action = 'punch_out'
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (member_id, last_punch_in))
                
                existing_punchout = cur.fetchone()
                
                if existing_punchout:
                    print(f"   ✅ Already has punch-out: {existing_punchout['timestamp']}")
                    print(f"   🔧 Just resetting member status\n")
                    
                    # Just reset status
                    cur.execute("""
                        UPDATE members
                        SET is_punched_in = FALSE,
                            status = 'offline'
                        WHERE id = %s
                    """, (member_id,))
                    
                else:
                    # Calculate auto punch-out time (8 hours after punch-in as default work day)
                    if last_punch_in:
                        auto_punchout = last_punch_in + timedelta(hours=8)
                        duration_minutes = 8 * 60  # 8 hours
                    else:
                        # auto_punchout = datetime.utcnow()
                        auto_punchout = datetime.now(IST)
                        duration_minutes = 0
                    
                    print(f"   ❌ No punch-out found")
                    print(f"   🔧 Creating auto punch-out at: {auto_punchout}")
                    print(f"   ⏱️  Duration: {duration_minutes} minutes ({duration_minutes//60} hours)\n")
                    
                    # Create punch-out record
                    cur.execute("""
                        INSERT INTO punch_logs (
                            company_id,
                            member_id,
                            email,
                            action,
                            timestamp,
                            duration_minutes,
                            status
                        ) VALUES (
                            12, %s, %s, 'punch_out', %s, %s, 'auto_cleanup'
                        )
                        RETURNING id
                    """, (member_id, email, auto_punchout, duration_minutes))
                    
                    punchout_log = cur.fetchone()
                    print(f"   ✅ Created punch-out log ID: {punchout_log['id']}")
                    
                    # Reset member status
                    cur.execute("""
                        UPDATE members
                        SET is_punched_in = FALSE,
                            status = 'offline',
                            last_punch_out_at = %s
                        WHERE id = %s
                    """, (auto_punchout, member_id))
                    
                    print(f"   ✅ Updated member status to offline\n")
            
            # Commit all changes
            conn.commit()
            
            print("="*70)
            print(f"✅ FIXED! All {len(members)} members have been reset")
            print("="*70)
            print("\n💡 What was done:")
            print("   1. Created auto punch-out records for sessions without punch-out")
            print("   2. Reset is_punched_in = FALSE for all stuck members")
            print("   3. Set status = 'offline' for all")
            print("\n🎯 Result:")
            print("   - Members can now punch in again normally")
            print("   - Attendance page will show correct status")
            print("   - Old sessions are properly closed")
            print("\n🔄 Refresh your attendance page to see the changes!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\n⚠️  Please make sure:")
        print("   1. You're running this from the backend directory")
        print("   2. The app.py file is in the same directory")
        print("   3. Your .env file has the correct DATABASE_URL")


if __name__ == '__main__':
    print("\n🚀 Starting immediate fix...\n")
    immediate_fix()
    print("\n✅ Done!\n")
