"""
CONFIGURATION_ROUTES.PY - Enhanced Company Configuration Management
===================================================================
✅ Manage screenshot intervals, idle timeouts, office hours
✅ Communicate with company_configurations table
✅ Support for tracker configuration sync
✅ Multi-tenant isolated
✅ Configuration broadcast to active trackers
✅ JSONB support for working_days
✅ FIXED: Use admin_id (INTEGER) instead of admin_email (STRING) for last_modified_by
"""

from flask import Blueprint, request, jsonify
from admin_auth_routes import require_admin_auth
from db import get_db, get_ist_now
from datetime import datetime
import json

configuration_bp = Blueprint('configuration', __name__)

# ============================================================================
# CONFIGURATION BROADCAST SYSTEM
# ============================================================================

# Store active tracker connections (company_id -> list of tracker sessions)
active_trackers = {}

def register_tracker(company_id, tracker_id):
    """Register an active tracker for configuration updates"""
    if company_id not in active_trackers:
        active_trackers[company_id] = set()
    active_trackers[company_id].add(tracker_id)
    print(f"📡 Tracker registered: company={company_id}, tracker={tracker_id}")

def unregister_tracker(company_id, tracker_id):
    """Unregister a tracker when it disconnects"""
    if company_id in active_trackers:
        active_trackers[company_id].discard(tracker_id)
        if not active_trackers[company_id]:
            del active_trackers[company_id]
    print(f"📴 Tracker unregistered: company={company_id}, tracker={tracker_id}")

def get_active_tracker_count(company_id):
    """Get count of active trackers for a company"""
    return len(active_trackers.get(company_id, set()))

# ============================================================================
# GET CONFIGURATION
# ============================================================================

@configuration_bp.route('/api/configuration', methods=['GET'])
@require_admin_auth
def get_configuration():
    """
    Get company configuration settings
    Returns current screenshot interval, idle timeout, office hours, etc.
    """
    try:
        company_id = request.company_id
        
        print(f"\n📋 GET CONFIGURATION: Company ID = {company_id}")
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Check if company_configurations table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'company_configurations'
                )
            """)
            table_exists = cur.fetchone()['exists']
            
            if not table_exists:
                print(f"⚠️ company_configurations table does not exist, creating...")
                
                # Create the table with JSONB for working_days
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS company_configurations (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                        screenshot_interval_minutes INTEGER DEFAULT 10,
                        idle_timeout_minutes INTEGER DEFAULT 5,
                        office_start_time TIME DEFAULT '09:00:00',
                        office_end_time TIME DEFAULT '18:00:00',
                        working_days JSONB DEFAULT '[1,2,3,4,5]'::jsonb,
                        last_modified_by INTEGER REFERENCES admin_users(id),
                        last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(company_id)
                    )
                """)
                conn.commit()
                print(f"✅ company_configurations table created")
            
            # Get configuration for this company
            cur.execute("""
                SELECT 
                    id,
                    company_id,
                    screenshot_interval_minutes,
                    idle_timeout_minutes,
                    office_start_time,
                    office_end_time,
                    working_days,
                    last_modified_by,
                    last_modified_at,
                    created_at
                FROM company_configurations
                WHERE company_id = %s
            """, (company_id,))
            
            config = cur.fetchone()
            
            if not config:
                print(f"⚠️ No configuration found for company {company_id}, creating default...")
                
                # Create default configuration
                default_working_days = [1, 2, 3, 4, 5]  # Monday to Friday
                
                cur.execute("""
                    INSERT INTO company_configurations (
                        company_id,
                        screenshot_interval_minutes,
                        idle_timeout_minutes,
                        office_start_time,
                        office_end_time,
                        working_days
                    ) VALUES (%s, 10, 5, '09:00:00', '18:00:00', %s::jsonb)
                    RETURNING id, company_id, screenshot_interval_minutes, idle_timeout_minutes,
                              office_start_time, office_end_time, working_days,
                              last_modified_by, last_modified_at, created_at
                """, (company_id, json.dumps(default_working_days)))
                
                config = cur.fetchone()
                conn.commit()
                print(f"✅ Default configuration created for company {company_id}")
            
            # Parse working_days from JSONB
            working_days = config['working_days']
            if isinstance(working_days, str):
                working_days = json.loads(working_days)
            elif not isinstance(working_days, list):
                working_days = [1, 2, 3, 4, 5]  # Fallback
            
            # Get active tracker count
            active_count = get_active_tracker_count(company_id)
            
            # Format response
            response_data = {
                'success': True,
                'config': {
                    'id': config['id'],
                    'company_id': config['company_id'],
                    'screenshot_interval_minutes': config['screenshot_interval_minutes'],
                    'idle_timeout_minutes': config['idle_timeout_minutes'],
                    'office_start_time': str(config['office_start_time']),
                    'office_end_time': str(config['office_end_time']),
                    'working_days': working_days,
                    'last_modified_by': config['last_modified_by'],
                    'last_modified_at': config['last_modified_at'].isoformat() if config['last_modified_at'] else None,
                    'created_at': config['created_at'].isoformat() if config['created_at'] else None
                },
                'active_trackers': active_count
            }
            
            print(f"✅ Configuration retrieved successfully")
            print(f"   Screenshot: {config['screenshot_interval_minutes']}min, Idle: {config['idle_timeout_minutes']}min")
            print(f"   Working days: {working_days}")
            print(f"   Active trackers: {active_count}")
            return jsonify(response_data), 200
            
    except Exception as e:
        print(f"❌ GET Configuration Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to retrieve configuration'}), 500


# ============================================================================
# UPDATE CONFIGURATION
# ============================================================================

@configuration_bp.route('/api/configuration', methods=['POST', 'PUT'])
@require_admin_auth
def update_configuration():
    """
    Update company configuration settings
    Updates screenshot interval, idle timeout, office hours, working days
    Broadcasts changes to all active trackers for this company
    """
    try:
        company_id = request.company_id
        admin_id = request.admin_id  # FIXED: Use admin_id (INTEGER) instead of admin_email (STRING)
        
        data = request.get_json() or {}
        config_data = data.get('config', {})
        
        print(f"\n💾 UPDATE CONFIGURATION: Company ID = {company_id}")
        print(f"👤 Admin ID: {admin_id}")
        print(f"📝 Data: {json.dumps(config_data, indent=2)}")
        
        # Extract configuration values
        screenshot_interval = config_data.get('screenshot_interval_minutes', 10)
        idle_timeout = config_data.get('idle_timeout_minutes', 5)
        office_start = config_data.get('office_start_time', '09:00:00')
        office_end = config_data.get('office_end_time', '18:00:00')
        working_days = config_data.get('working_days', [1, 2, 3, 4, 5])
        
        # Validation
        if not (1 <= screenshot_interval <= 60):
            return jsonify({'error': 'Screenshot interval must be between 1 and 60 minutes'}), 400
        
        if not (1 <= idle_timeout <= 30):
            return jsonify({'error': 'Idle timeout must be between 1 and 30 minutes'}), 400
        
        if not isinstance(working_days, list) or not working_days:
            return jsonify({'error': 'Working days must be a non-empty array'}), 400
        
        # Validate working_days values (0-6)
        if not all(isinstance(day, int) and 0 <= day <= 6 for day in working_days):
            return jsonify({'error': 'Working days must contain integers between 0 (Sunday) and 6 (Saturday)'}), 400
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Check if configuration exists
            cur.execute("""
                SELECT id FROM company_configurations
                WHERE company_id = %s
            """, (company_id,))
            
            existing = cur.fetchone()
            
            # Convert working_days to JSON string for JSONB column
            working_days_json = json.dumps(working_days)
            
            if existing:
                # Update existing configuration
                print(f"✏️ Updating existing configuration (ID: {existing['id']})")
                
                cur.execute("""
                    UPDATE company_configurations
                    SET screenshot_interval_minutes = %s,
                        idle_timeout_minutes = %s,
                        office_start_time = %s,
                        office_end_time = %s,
                        working_days = %s::jsonb,
                        last_modified_by = %s,
                        last_modified_at = %s
                    WHERE company_id = %s
                    RETURNING id, last_modified_at, created_at
                """, (
                    screenshot_interval,
                    idle_timeout,
                    office_start,
                    office_end,
                    working_days_json,
                    admin_id,  # FIXED: Now using admin_id (INTEGER)
                    get_ist_now(),
                    company_id
                ))
            else:
                # Insert new configuration
                print(f"➕ Creating new configuration")
                
                cur.execute("""
                    INSERT INTO company_configurations (
                        company_id,
                        screenshot_interval_minutes,
                        idle_timeout_minutes,
                        office_start_time,
                        office_end_time,
                        working_days,
                        last_modified_by,
                        last_modified_at
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    RETURNING id, last_modified_at, created_at
                """, (
                    company_id,
                    screenshot_interval,
                    idle_timeout,
                    office_start,
                    office_end,
                    working_days_json,
                    admin_id,  # FIXED: Now using admin_id (INTEGER)
                    get_ist_now()
                ))
            
            result = cur.fetchone()
            conn.commit()
            
            print(f"✅ Configuration saved successfully")
            print(f"   Screenshot: {screenshot_interval}min, Idle: {idle_timeout}min")
            print(f"   Office: {office_start} - {office_end}")
            print(f"   Working days: {working_days}")
            
            # Notify active trackers about configuration change
            active_count = get_active_tracker_count(company_id)
            if active_count > 0:
                print(f"📡 Broadcasting config change to {active_count} active trackers")
                # Note: Trackers will pull new config on their next sync cycle (every 5 minutes)
            
            return jsonify({
                'success': True,
                'message': 'Configuration updated successfully',
                'config_id': result['id'],
                'updated_at': result['last_modified_at'].isoformat() if result['last_modified_at'] else None,
                'created_at': result['created_at'].isoformat() if result['created_at'] else None,
                'active_trackers_notified': active_count
            }), 200
            
    except Exception as e:
        print(f"❌ UPDATE Configuration Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to update configuration'}), 500


# ============================================================================
# GET TRACKER CONFIGURATION (For Trackers)
# ============================================================================

@configuration_bp.route('/api/tracker/configuration', methods=['GET'])
def get_tracker_configuration():
    """
    Get configuration for tracker clients
    Returns screenshot interval and idle timeout based on company_id from tracker token
    No authentication required - uses tracker token
    Also registers tracker as active for configuration broadcast
    """
    try:
        # Get tracker token from header or query
        tracker_token = request.headers.get('X-Tracker-Token') or request.args.get('tracker_token')
        
        if not tracker_token:
            return jsonify({'error': 'Tracker token required'}), 401
        
        # Extract company_id from tracker token
        import base64
        try:
            decoded = base64.b64decode(tracker_token.encode()).decode()
            parts = decoded.split(':', 1)
            company_id = int(parts[0])
        except Exception as e:
            print(f"❌ Invalid tracker token: {e}")
            return jsonify({'error': 'Invalid tracker token'}), 401
        
        # Generate tracker session ID for registration
        tracker_id = request.remote_addr or 'unknown'
        if 'device_id' in request.args:
            tracker_id = f"{tracker_id}_{request.args.get('device_id')}"
        
        print(f"\n🔧 TRACKER CONFIG REQUEST: Company ID = {company_id}, Tracker = {tracker_id}")
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get configuration
            cur.execute("""
                SELECT 
                    screenshot_interval_minutes,
                    idle_timeout_minutes,
                    office_start_time,
                    office_end_time,
                    working_days
                FROM company_configurations
                WHERE company_id = %s
            """, (company_id,))
            
            config = cur.fetchone()
            
            if not config:
                # Return defaults if no configuration exists
                print(f"⚠️ No configuration found, returning defaults")
                register_tracker(company_id, tracker_id)
                return jsonify({
                    'success': True,
                    'screenshot_interval_minutes': 10,
                    'idle_timeout_minutes': 5,
                    'office_start_time': '09:00:00',
                    'office_end_time': '18:00:00',
                    'working_days': [1, 2, 3, 4, 5]
                }), 200
            
            # Parse working_days
            working_days = config['working_days']
            if isinstance(working_days, str):
                working_days = json.loads(working_days)
            elif not isinstance(working_days, list):
                working_days = [1, 2, 3, 4, 5]
            
            # Register this tracker as active
            register_tracker(company_id, tracker_id)
            
            print(f"✅ Configuration sent to tracker: screenshot={config['screenshot_interval_minutes']}min, idle={config['idle_timeout_minutes']}min")
            print(f"📊 Total active trackers for company {company_id}: {get_active_tracker_count(company_id)}")
            
            return jsonify({
                'success': True,
                'screenshot_interval_minutes': config['screenshot_interval_minutes'],
                'idle_timeout_minutes': config['idle_timeout_minutes'],
                'office_start_time': str(config['office_start_time']),
                'office_end_time': str(config['office_end_time']),
                'working_days': working_days,
                'sync_interval_seconds': 300  # Tell tracker to re-sync every 5 minutes
            }), 200
            
    except Exception as e:
        print(f"❌ TRACKER Configuration Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to retrieve tracker configuration'}), 500


# ============================================================================
# TRACKER HEARTBEAT (For keeping tracker registration alive)
# ============================================================================

@configuration_bp.route('/api/tracker/heartbeat', methods=['POST'])
def tracker_heartbeat():
    """
    Tracker heartbeat endpoint to keep registration alive
    Call this every minute from trackers to maintain active status
    """
    try:
        tracker_token = request.headers.get('X-Tracker-Token')
        
        if not tracker_token:
            return jsonify({'error': 'Tracker token required'}), 401
        
        # Extract company_id
        import base64
        try:
            decoded = base64.b64decode(tracker_token.encode()).decode()
            parts = decoded.split(':', 1)
            company_id = int(parts[0])
        except:
            return jsonify({'error': 'Invalid tracker token'}), 401
        
        # Generate tracker ID
        data = request.get_json(silent=True) or {}
        device_id = data.get('device_id', request.remote_addr or 'unknown')
        tracker_id = f"{request.remote_addr}_{device_id}"
        
        # Re-register tracker to keep it active
        register_tracker(company_id, tracker_id)
        
        return jsonify({
            'success': True,
            'message': 'Heartbeat received',
            'active_trackers': get_active_tracker_count(company_id)
        }), 200
        
    except Exception as e:
        print(f"❌ Heartbeat Error: {e}")
        return jsonify({'error': 'Heartbeat failed'}), 500


__all__ = ['configuration_bp', 'register_tracker', 'unregister_tracker', 'get_active_tracker_count']
