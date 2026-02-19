"""
ATTENDANCE_ROUTES.PY - Complete Attendance System with Punch In/Out
====================================================================
✅ Punch In/Out endpoints that write to punch_logs table
✅ One punch per day rule (12:00 AM to 12:00 AM)
✅ Updates members table (is_punched_in, last_punch_in_at, last_punch_out_at)
✅ Stores to DB: punch_in_time, punch_out_time, duration_minutes, punch_date
✅ Returns data for UI display
"""

from flask import Blueprint, request, jsonify
from admin_auth_routes import require_admin_auth
from db import get_db, get_ist_now, IST
from datetime import datetime, timedelta
from collections import defaultdict
import calendar
import traceback

attendance_bp = Blueprint('attendance', __name__)

# ============================================================================
# PUNCH IN ENDPOINT - Stores to Database
# ============================================================================

@attendance_bp.route('/api/attendance/punch-in', methods=['POST'])
def punch_in():
    """
    Punch in endpoint - Creates record in punch_logs table
    
    Request: {"member_email": "user@example.com", "company_id": 1}
    Response: {"success": true, "punch_in_time": "2026-01-20T09:00:00", ...}
    
    Rules:
    - One punch-in per day (12:00 AM to 12:00 AM)
    - Creates record with punch_in_time, sets punch_out_time to NULL
    - Updates members.is_punched_in = TRUE
    """
    try:
        data = request.get_json()
        member_email = data.get('member_email')
        company_id = data.get('company_id')
        
        print(f"🟢 PUNCH-IN REQUEST: email={member_email}, company_id={company_id}")
        
        if not member_email or not company_id:
            return jsonify({'error': 'Member email and company ID required'}), 400
        
        punch_time = get_ist_now()
        punch_date_today = punch_time.date()
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get member
            cur.execute("""
                SELECT id, name FROM members
                WHERE company_id = %s AND email = %s AND is_active = TRUE
            """, (company_id, member_email))
            
            member = cur.fetchone()
            if not member:
                print(f"❌ PUNCH-IN: Member not found - {member_email}")
                return jsonify({'error': 'Member not found or inactive'}), 404
            
            member_id = member['id']
            member_name = member['name']
            
            # Check if already punched in today (punch_date = today AND punch_out_time IS NULL)
            cur.execute("""
                SELECT id, punch_in_time 
                FROM punch_logs
                WHERE company_id = %s 
                  AND member_id = %s 
                  AND punch_date = %s
                  AND punch_out_time IS NULL
                LIMIT 1
            """, (company_id, member_id, punch_date_today))
            
            existing_punch = cur.fetchone()
            
            if existing_punch:
                print(f"⚠️ PUNCH-IN: Already punched in today - member_id={member_id}")
                return jsonify({
                    'error': 'Already punched in today. You can only punch in once per day (12:00 AM to 12:00 AM).',
                    'existing_punch_in': existing_punch['punch_in_time'].isoformat()
                }), 400
            
            # Insert new punch log with punch_in_time, punch_out_time = NULL
            cur.execute("""
                INSERT INTO punch_logs (
                    company_id, 
                    member_id, 
                    punch_in_time, 
                    punch_out_time, 
                    duration_minutes, 
                    punch_date, 
                    status,
                    created_at
                )
                VALUES (%s, %s, %s, NULL, NULL, %s, 'punched_in', %s)
                RETURNING id, punch_in_time, punch_date
            """, (company_id, member_id, punch_time, punch_date_today, punch_time))
            
            punch_log = cur.fetchone()
            
            # Update members table
            cur.execute("""
                UPDATE members
                SET is_punched_in = TRUE,
                    last_punch_in_at = %s,
                    current_punch_in_time = %s,
                    status = 'active'
                WHERE id = %s
            """, (punch_time, punch_time, member_id))
            
            conn.commit()
            
            print(f"✅ PUNCH-IN SUCCESS: {member_name} - punch_id={punch_log['id']}, time={punch_log['punch_in_time']}")
            
            return jsonify({
                'success': True,
                'message': f'Punched in successfully at {punch_time.strftime("%I:%M %p")}',
                'punch_id': punch_log['id'],
                'punch_in_time': punch_log['punch_in_time'].isoformat(),
                'punch_date': punch_log['punch_date'].isoformat(),
                'member_name': member_name,
                'member_id': member_id
            }), 200
            
    except Exception as e:
        print(f"❌ PUNCH-IN ERROR: {e}")
        traceback.print_exc()
        return jsonify({'error': 'Failed to punch in', 'details': str(e)}), 500


# ============================================================================
# PUNCH OUT ENDPOINT - Updates Database
# ============================================================================

@attendance_bp.route('/api/attendance/punch-out', methods=['POST'])
def punch_out():
    """
    Punch out endpoint - Updates punch_logs record
    
    Request: {"member_email": "user@example.com", "company_id": 1}
    Response: {"success": true, "duration": "8h 30m", ...}
    
    Rules:
    - Finds today's punch-in record (punch_out_time IS NULL)
    - Updates punch_out_time and calculates duration_minutes
    - Updates members.is_punched_in = FALSE
    """
    try:
        data = request.get_json()
        member_email = data.get('member_email')
        company_id = data.get('company_id')
        
        print(f"🔴 PUNCH-OUT REQUEST: email={member_email}, company_id={company_id}")
        
        if not member_email or not company_id:
            return jsonify({'error': 'Member email and company ID required'}), 400
        
        punch_out_time = get_ist_now()
        punch_date_today = punch_out_time.date()
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get member
            cur.execute("""
                SELECT id, name FROM members
                WHERE company_id = %s AND email = %s AND is_active = TRUE
            """, (company_id, member_email))
            
            member = cur.fetchone()
            if not member:
                print(f"❌ PUNCH-OUT: Member not found - {member_email}")
                return jsonify({'error': 'Member not found or inactive'}), 404
            
            member_id = member['id']
            member_name = member['name']
            
            # Find today's active punch-in (punch_out_time IS NULL)
            cur.execute("""
                SELECT id, punch_in_time, punch_date
                FROM punch_logs
                WHERE company_id = %s 
                  AND member_id = %s 
                  AND punch_date = %s
                  AND punch_out_time IS NULL
                ORDER BY punch_in_time DESC
                LIMIT 1
            """, (company_id, member_id, punch_date_today))
            
            punch_log = cur.fetchone()
            
            if not punch_log:
                print(f"⚠️ PUNCH-OUT: No active punch-in found - member_id={member_id}")
                return jsonify({
                    'error': 'No active punch-in found for today. Please punch in first.'
                }), 400
            
            punch_log_id = punch_log['id']
            punch_in_time = punch_log['punch_in_time']
            
            # Ensure timezone
            if punch_in_time.tzinfo is None:
                import pytz
                punch_in_time = pytz.UTC.localize(punch_in_time)
            punch_in_ist = punch_in_time.astimezone(IST)
            
            # Calculate duration
            duration_seconds = int((punch_out_time - punch_in_ist).total_seconds())
            duration_minutes = duration_seconds // 60
            
            # Update punch log
            cur.execute("""
                UPDATE punch_logs
                SET punch_out_time = %s,
                    duration_minutes = %s,
                    status = 'punched_out'
                WHERE id = %s
                RETURNING id, punch_in_time, punch_out_time, duration_minutes, punch_date
            """, (punch_out_time, duration_minutes, punch_log_id))
            
            updated_punch = cur.fetchone()
            
            # Update members table
            cur.execute("""
                UPDATE members
                SET is_punched_in = FALSE,
                    last_punch_out_at = %s,
                    current_punch_in_time = NULL,
                    status = 'offline'
                WHERE id = %s
            """, (punch_out_time, member_id))
            
            conn.commit()
            
            # Format duration for display
            hours = duration_minutes // 60
            minutes = duration_minutes % 60
            duration_str = f"{hours}h {minutes}m"
            
            print(f"✅ PUNCH-OUT SUCCESS: {member_name} - duration={duration_str}")
            
            return jsonify({
                'success': True,
                'message': f'Punched out successfully. Work duration: {duration_str}',
                'punch_id': updated_punch['id'],
                'punch_in_time': updated_punch['punch_in_time'].isoformat(),
                'punch_out_time': updated_punch['punch_out_time'].isoformat(),
                'duration_minutes': duration_minutes,
                'duration_seconds': duration_seconds,
                'duration_formatted': duration_str,
                'punch_date': updated_punch['punch_date'].isoformat(),
                'member_name': member_name,
                'member_id': member_id
            }), 200
            
    except Exception as e:
        print(f"❌ PUNCH-OUT ERROR: {e}")
        traceback.print_exc()
        return jsonify({'error': 'Failed to punch out', 'details': str(e)}), 500


# ============================================================================
# GET ALL MEMBERS ATTENDANCE STATUS
# ============================================================================

@attendance_bp.route('/api/attendance/members', methods=['GET'])
@require_admin_auth
def get_members_attendance():
    """Get current attendance status for all members"""
    try:
        company_id = request.company_id
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get today's punch data
            cur.execute("""
                WITH today_punches AS (
                    SELECT 
                        member_id,
                        MAX(punch_in_time) as last_punch_in,
                        MAX(punch_out_time) as last_punch_out,
                        SUM(COALESCE(duration_minutes, 0)) as total_minutes
                    FROM punch_logs
                    WHERE company_id = %s 
                      AND punch_date = CURRENT_DATE
                    GROUP BY member_id
                )
                SELECT 
                    m.id,
                    m.name,
                    m.email,
                    m.position,
                    m.department,
                    m.status,
                    m.is_punched_in,
                    m.last_punch_in_at,
                    m.last_punch_out_at,
                    COALESCE(tp.last_punch_in, m.last_punch_in_at) as punch_in_time,
                    COALESCE(tp.last_punch_out, m.last_punch_out_at) as punch_out_time,
                    COALESCE(tp.total_minutes, 0) as today_minutes,
                    m.last_activity_at, m.last_heartbeat_at
                FROM members m
                LEFT JOIN today_punches tp ON m.id = tp.member_id
                WHERE m.company_id = %s AND m.is_active = TRUE
                ORDER BY m.name
            """, (company_id, company_id))
            
            members = cur.fetchall()
            
            members_list = []
            for member in members:
                today_hours = float(member['today_minutes']) / 60.0 if member['today_minutes'] else 0.0
                
                # Determine live status from recent activity
                try:
                    derived_status = 'offline'
                    now = get_ist_now()
                    last_activity = member.get('last_activity_at')
                    last_heartbeat = member.get('last_heartbeat_at')
                    latest_ts = last_activity or last_heartbeat
                    if member['is_punched_in']:
                        if latest_ts:
                            if latest_ts.tzinfo is None:
                                import pytz
                                latest_ts = pytz.UTC.localize(latest_ts)
                            latest_ist = latest_ts.astimezone(IST)
                            diff_seconds = (now - latest_ist).total_seconds()
                            if diff_seconds <= 120:
                                derived_status = 'active'
                            elif diff_seconds <= 600:
                                derived_status = 'idle'
                            else:
                                derived_status = 'offline'
                        else:
                            # No activity timestamps, assume active while punched in
                            derived_status = 'active'
                    else:
                        derived_status = 'offline'
                except Exception:
                    derived_status = member.get('status', 'offline')
                
                # Add current session if punched in
                if member['is_punched_in'] and member['punch_in_time']:
                    now = get_ist_now()
                    punch_in = member['punch_in_time']
                    
                    if punch_in.tzinfo is None:
                        import pytz
                        punch_in = pytz.UTC.localize(punch_in)
                    punch_in_ist = punch_in.astimezone(IST)
                    
                    current_session_seconds = (now - punch_in_ist).total_seconds()
                    today_hours += current_session_seconds / 3600.0
                
                # Convert punch times to IST ISO strings (include tz)
                def to_ist_iso(dt):
                    if not dt:
                        return None
                    if dt.tzinfo is None:
                        import pytz
                        dt = pytz.UTC.localize(dt)
                    return dt.astimezone(IST).isoformat()
                
                members_list.append({
                    'id': member['id'],
                    'name': member['name'],
                    'email': member['email'],
                    'position': member['position'],
                    'department': member['department'],
                    'status': derived_status,
                    'is_punched_in': member['is_punched_in'],
                    'punch_in_time': to_ist_iso(member['punch_in_time']),
                    'punch_out_time': to_ist_iso(member['punch_out_time']),
                    'today_hours': round(today_hours, 2)
                })
            
            return jsonify({'success': True, 'members': members_list}), 200
            
    except Exception as e:
        print(f"❌ Get members attendance error: {e}")
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch attendance data'}), 500


# ============================================================================
# GET MEMBER ATTENDANCE HISTORY
# ============================================================================

@attendance_bp.route('/api/attendance/member/<int:member_id>', methods=['GET'])
@require_admin_auth
def get_member_attendance(member_id):
    """Get detailed attendance history for a member"""
    try:
        company_id = request.company_id
        
        end_date_str = request.args.get('end_date')
        start_date_str = request.args.get('start_date')
        
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else datetime.now(IST).date()
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else end_date - timedelta(days=30)
        
        with get_db() as conn:
            cur = conn.cursor()
            
            cur.execute("SELECT name, email, position, department FROM members WHERE id = %s AND company_id = %s", (member_id, company_id))
            member = cur.fetchone()
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            
            cur.execute("SELECT working_days FROM company_configurations WHERE company_id = %s", (company_id,))
            config = cur.fetchone()
            working_days = config['working_days'] if config and config['working_days'] else [1, 2, 3, 4, 5]
            
            cur.execute("""
                SELECT punch_date, punch_in_time, punch_out_time, COALESCE(duration_minutes, 0) as duration_minutes
                FROM punch_logs
                WHERE company_id = %s AND member_id = %s AND punch_date BETWEEN %s AND %s
                ORDER BY punch_in_time
            """, (company_id, member_id, start_date, end_date))
            
            punch_logs = cur.fetchall()
            
            daily_data = defaultdict(lambda: {'punch_ins': [], 'punch_outs': [], 'total_minutes': 0})
            for log in punch_logs:
                date_key = log['punch_date']
                if log['punch_in_time']:
                    daily_data[date_key]['punch_ins'].append(log['punch_in_time'])
                if log['punch_out_time']:
                    daily_data[date_key]['punch_outs'].append(log['punch_out_time'])
                daily_data[date_key]['total_minutes'] += log['duration_minutes']
            
            daily_records = []
            total_hours = 0
            days_present = 0
            
            current_date = start_date
            while current_date <= end_date:
                is_working_day = current_date.weekday() in working_days
                
                if current_date in daily_data:
                    data = daily_data[current_date]
                    first_punch_in = min(data['punch_ins']) if data['punch_ins'] else None
                    last_punch_out = max(data['punch_outs']) if data['punch_outs'] else None
                    hours = data['total_minutes'] / 60.0
                    total_hours += hours
                    if first_punch_in:
                        days_present += 1
                    
                    daily_records.append({
                        'date': current_date.isoformat(),
                        'day': calendar.day_name[current_date.weekday()],
                        'punch_in': first_punch_in.strftime('%H:%M:%S') if first_punch_in else 'N/A',
                        'punch_out': last_punch_out.strftime('%H:%M:%S') if last_punch_out else 'N/A',
                        'duration': f"{int(hours)}h {int((hours % 1) * 60)}m",
                        'duration_seconds': int(data['total_minutes'] * 60),
                        'is_working_day': is_working_day,
                        'status': 'Present' if first_punch_in else ('Absent' if is_working_day else 'Holiday/Weekend')
                    })
                else:
                    daily_records.append({
                        'date': current_date.isoformat(),
                        'day': calendar.day_name[current_date.weekday()],
                        'punch_in': 'N/A',
                        'punch_out': 'N/A',
                        'duration': '0h 0m',
                        'duration_seconds': 0,
                        'is_working_day': is_working_day,
                        'status': 'Absent' if is_working_day else 'Holiday/Weekend'
                    })
                
                current_date += timedelta(days=1)
            
            total_days = (end_date - start_date).days + 1
            working_days_count = sum(1 for r in daily_records if r['is_working_day'])
            
            return jsonify({
                'success': True,
                'member': {'id': member_id, 'name': member['name'], 'email': member['email'], 'position': member['position'], 'department': member['department']},
                'date_range': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
                'statistics': {
                    'total_days': total_days,
                    'working_days': working_days_count,
                    'days_present': days_present,
                    'days_absent': working_days_count - days_present,
                    'attendance_percentage': round((days_present / working_days_count * 100) if working_days_count > 0 else 0, 2),
                    'total_hours': round(total_hours, 2),
                    'average_hours_per_day': round(total_hours / days_present if days_present > 0 else 0, 2)
                },
                'daily_records': daily_records
            }), 200
            
    except Exception as e:
        print(f"❌ Member attendance error: {e}")
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch attendance history'}), 500


# ============================================================================
# GET ATTENDANCE ANALYTICS
# ============================================================================

@attendance_bp.route('/api/attendance/analytics/<int:member_id>', methods=['GET'])
@require_admin_auth
def get_attendance_analytics(member_id):
    """Get attendance analytics for charts"""
    try:
        company_id = request.company_id
        view_type = request.args.get('view', 'daily').lower()
        
        end_date_str = request.args.get('end_date')
        start_date_str = request.args.get('start_date')
        
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else datetime.now(IST).date()
        
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            if view_type == 'monthly':
                start_date = end_date - timedelta(days=365)
            elif view_type == 'weekly':
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=30)
        
        with get_db() as conn:
            cur = conn.cursor()
            
            cur.execute("SELECT name FROM members WHERE id = %s AND company_id = %s", (member_id, company_id))
            member = cur.fetchone()
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            
            cur.execute("""
                SELECT punch_date, SUM(COALESCE(duration_minutes, 0)) as total_minutes
                FROM punch_logs
                WHERE company_id = %s AND member_id = %s AND punch_date BETWEEN %s AND %s
                GROUP BY punch_date
                ORDER BY punch_date ASC
            """, (company_id, member_id, start_date, end_date))
            
            daily_data = cur.fetchall()
            
            if view_type == 'daily':
                result = [
                    {
                        'date': record['punch_date'].isoformat(),
                        'hours': round(float(record['total_minutes']) / 60.0, 2),
                        'day_name': calendar.day_name[record['punch_date'].weekday()]
                    }
                    for record in daily_data
                ]
                return jsonify({'success': True, 'view': 'daily', 'member_name': member['name'], 'data': result}), 200
            
            elif view_type == 'weekly':
                weekly_chart = defaultdict(lambda: {'minutes': 0, 'days': 0})
                for record in daily_data:
                    date = record['punch_date']
                    minutes = float(record['total_minutes']) if record['total_minutes'] else 0
                    week_key = f"{date.year}-W{date.isocalendar()[1]:02d}"
                    weekly_chart[week_key]['minutes'] += minutes
                    weekly_chart[week_key]['days'] += 1
                
                result = [
                    {
                        'week': week,
                        'total_hours': round(data['minutes'] / 60.0, 2),
                        'days_present': data['days'],
                        'avg_hours_per_day': round((data['minutes'] / 60.0) / data['days'], 2) if data['days'] > 0 else 0
                    }
                    for week, data in sorted(weekly_chart.items())
                ]
                return jsonify({'success': True, 'view': 'weekly', 'member_name': member['name'], 'data': result}), 200
            
            elif view_type == 'monthly':
                monthly_chart = defaultdict(lambda: {'minutes': 0, 'days': 0})
                for record in daily_data:
                    date = record['punch_date']
                    minutes = float(record['total_minutes']) if record['total_minutes'] else 0
                    month_key = date.strftime('%Y-%m')
                    monthly_chart[month_key]['minutes'] += minutes
                    monthly_chart[month_key]['days'] += 1
                
                result = [
                    {
                        'month': month,
                        'total_hours': round(data['minutes'] / 60.0, 2),
                        'days_present': data['days'],
                        'avg_hours_per_day': round((data['minutes'] / 60.0) / data['days'], 2) if data['days'] > 0 else 0
                    }
                    for month, data in sorted(monthly_chart.items())
                ]
                return jsonify({'success': True, 'view': 'monthly', 'member_name': member['name'], 'data': result}), 200
            
            return jsonify({'error': 'Invalid view type'}), 400
            
    except Exception as e:
        print(f"❌ Analytics error: {e}")
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch analytics'}), 500


__all__ = ['attendance_bp']
