"""
ANALYTICS_ROUTES.PY - Advanced Analytics (Synchronous + psycopg2)
==================================================================
✅ psycopg2 ONLY
✅ Member-specific analytics
✅ PostgreSQL aggregations
✅ FIXED: Uses admin_auth for proper authentication
✅ FIXED: Changed activity_logs to activity_log to match schema
"""

from flask import Blueprint, request, jsonify
from admin_auth_routes import require_admin_auth
from db import get_db
from datetime import datetime, timedelta

analytics_bp = Blueprint('analytics', __name__)

# ============================================================================
# MEMBER ANALYTICS
# ============================================================================

@analytics_bp.route('/analytics/member/<int:member_id>', methods=['GET'])
@require_admin_auth
def get_member_analytics(member_id):
    """Get detailed analytics for a specific member"""
    try:
        company_id = request.company_id
        start_date = request.args.get('start_date', (datetime.utcnow() - timedelta(days=30)).isoformat())
        end_date = request.args.get('end_date', datetime.utcnow().isoformat())
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Verify member belongs to company
            cur.execute(
                "SELECT id, name, email FROM members WHERE id = %s AND company_id = %s",
                (member_id, company_id)
            )
            member = cur.fetchone()
            
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            
            # Total activity stats - FIXED: activity_log (not activity_logs)
            cur.execute(
                """
                SELECT 
                    COUNT(*) as total_activities,
                    COALESCE(SUM(total_seconds), 0) / 3600.0 as total_hours,
                    COUNT(DISTINCT DATE(timestamp)) as active_days
                FROM activity_log
                WHERE member_id = %s 
                  AND timestamp >= %s 
                  AND timestamp <= %s
                """,
                (member_id, start_date, end_date)
            )
            stats = cur.fetchone()
            
            # Top apps - FIXED: activity_log (not activity_logs)
            cur.execute(
                """
                SELECT 
                    current_process as app_name,
                    COUNT(*) as count,
                    COALESCE(SUM(total_seconds), 0) / 3600.0 as hours
                FROM activity_log
                WHERE member_id = %s 
                  AND timestamp >= %s 
                  AND timestamp <= %s
                  AND current_process IS NOT NULL
                GROUP BY current_process
                ORDER BY hours DESC
                LIMIT 10
                """,
                (member_id, start_date, end_date)
            )
            top_apps = cur.fetchall()
            
            # Daily activity - FIXED: activity_log (not activity_logs)
            cur.execute(
                """
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as activity_count,
                    COALESCE(SUM(total_seconds), 0) / 3600.0 as hours
                FROM activity_log
                WHERE member_id = %s 
                  AND timestamp >= %s 
                  AND timestamp <= %s
                GROUP BY date
                ORDER BY date
                """,
                (member_id, start_date, end_date)
            )
            daily_activity = cur.fetchall()
            
            return jsonify({
                'success': True,
                'member': member,
                'stats': stats,
                'top_apps': top_apps,
                'daily_activity': daily_activity
            }), 200
    
    except Exception as e:
        print(f"❌ Member analytics error: {e}")
        return jsonify({'error': 'Failed to fetch member analytics'}), 500


# ============================================================================
# PRODUCTIVITY TRENDS
# ============================================================================

@analytics_bp.route('/analytics/productivity-trends', methods=['GET'])
@require_admin_auth
def get_productivity_trends():
    """Get productivity trends over time"""
    try:
        company_id = request.company_id
        days = int(request.args.get('days', 30))
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # FIXED: activity_log (not activity_logs)
            cur.execute(
                """
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(DISTINCT member_id) as active_members,
                    COUNT(*) as total_activities,
                    COALESCE(SUM(total_seconds), 0) / 3600.0 as total_hours,
                    COALESCE(AVG(total_seconds), 0) as avg_duration_seconds
                FROM activity_log
                WHERE company_id = %s 
                  AND timestamp >= %s
                GROUP BY date
                ORDER BY date
                """,
                (company_id, start_date)
            )
            trends = cur.fetchall()
            
            return jsonify({
                'success': True,
                'trends': trends
            }), 200
    
    except Exception as e:
        print(f"❌ Productivity trends error: {e}")
        return jsonify({'error': 'Failed to fetch productivity trends'}), 500


# ============================================================================
# APPLICATION USAGE
# ============================================================================

@analytics_bp.route('/analytics/app-usage', methods=['GET'])
@require_admin_auth
def get_app_usage():
    """Get application usage breakdown"""
    try:
        company_id = request.company_id
        start_date = request.args.get('start_date', (datetime.utcnow() - timedelta(days=7)).isoformat())
        end_date = request.args.get('end_date', datetime.utcnow().isoformat())
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # FIXED: activity_log (not activity_logs)
            cur.execute(
                """
                SELECT 
                    current_process as app_name,
                    COUNT(*) as usage_count,
                    COUNT(DISTINCT member_id) as unique_users,
                    COALESCE(SUM(total_seconds), 0) / 3600.0 as total_hours,
                    COALESCE(AVG(total_seconds), 0) as avg_duration_seconds
                FROM activity_log
                WHERE company_id = %s 
                  AND timestamp >= %s 
                  AND timestamp <= %s
                  AND current_process IS NOT NULL
                GROUP BY current_process
                ORDER BY total_hours DESC
                """,
                (company_id, start_date, end_date)
            )
            apps = cur.fetchall()
            
            return jsonify({
                'success': True,
                'apps': apps
            }), 200
    
    except Exception as e:
        print(f"❌ App usage error: {e}")
        return jsonify({'error': 'Failed to fetch app usage'}), 500


# ============================================================================
# ATTENDANCE ANALYTICS
# ============================================================================

@analytics_bp.route('/analytics/attendance', methods=['GET'])
@require_admin_auth
def get_attendance_analytics():
    """Get attendance analytics for a member with raw data"""
    try:
        company_id = request.company_id
        member_id = request.args.get('member_id')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Get IST dates if not provided
        from datetime import timezone
        ist_offset = timezone(timedelta(hours=5, minutes=30))
        ist_now = datetime.now(ist_offset)
        
        if not start_date_str:
            start_date = (ist_now - timedelta(days=30)).date()
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            
        if not end_date_str:
            end_date = ist_now.date()
        else:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get raw attendance records
            query = """
                SELECT 
                    pl.id,
                    pl.member_id,
                    m.name as member_name,
                    pl.punch_date as date,
                    pl.punch_in_time,
                    pl.punch_out_time,
                    pl.duration_minutes,
                    pl.status
                FROM punch_logs pl
                JOIN members m ON pl.member_id = m.id
                WHERE pl.company_id = %s 
                  AND pl.punch_date >= %s 
                  AND pl.punch_date <= %s
            """
            params = [company_id, start_date, end_date]
            
            if member_id:
                query += " AND pl.member_id = %s"
                params.append(member_id)
            
            query += " ORDER BY pl.punch_date DESC, pl.punch_in_time DESC"
            
            cur.execute(query, params)
            attendance_records = cur.fetchall()
            
            return jsonify({
                'success': True,
                'records': attendance_records,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }), 200
    
    except Exception as e:
        print(f"❌ Attendance analytics error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch attendance analytics', 'details': str(e)}), 500


# ============================================================================
# ACTIVITY ANALYTICS  
# ============================================================================

@analytics_bp.route('/analytics/activity', methods=['GET'])
@require_admin_auth
def get_activity_analytics():
    """Get activity analytics (active/idle time) for a member"""
    try:
        company_id = request.company_id
        member_id = request.args.get('member_id')
        start_date = request.args.get('start_date', (datetime.utcnow() - timedelta(days=7)).isoformat())
        end_date = request.args.get('end_date', datetime.utcnow().isoformat())
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        
        if not member_id:
            return jsonify({'error': 'member_id is required'}), 400
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get activity logs with pagination - FIXED: activity_log (not activity_logs)
            cur.execute(
                """
                SELECT 
                    id,
                    timestamp,
                    current_window as window_title,
                    current_process as process_name,
                    is_idle,
                    locked,
                    total_seconds as duration_seconds,
                    timestamp::date as tracking_date
                FROM activity_log
                WHERE company_id = %s 
                  AND member_id = %s
                  AND timestamp >= %s 
                  AND timestamp <= %s
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
                """,
                (company_id, member_id, start_date, end_date, limit, offset)
            )
            logs = cur.fetchall()
            
            # Get total count for pagination - FIXED: activity_log (not activity_logs)
            cur.execute(
                """
                SELECT COUNT(*) as total
                FROM activity_log
                WHERE company_id = %s 
                  AND member_id = %s
                  AND timestamp >= %s 
                  AND timestamp <= %s
                """,
                (company_id, member_id, start_date, end_date)
            )
            total = cur.fetchone()['total']
            
            return jsonify({
                'success': True,
                'logs': logs,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'pages': (total + limit - 1) // limit
                }
            }), 200
    
    except Exception as e:
        print(f"❌ Activity analytics error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch activity analytics', 'details': str(e)}), 500


# ============================================================================
# APPLICATION ANALYTICS
# ============================================================================

@analytics_bp.route('/analytics/apps', methods=['GET'])
@require_admin_auth
def get_apps_analytics():
    """Get detailed application usage analytics"""
    try:
        company_id = request.company_id
        member_id = request.args.get('member_id')
        start_date = request.args.get('start_date', (datetime.utcnow() - timedelta(days=7)).isoformat())
        end_date = request.args.get('end_date', datetime.utcnow().isoformat())
        
        if not member_id:
            return jsonify({'error': 'member_id is required'}), 400
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get raw application logs - FIXED: activity_log (not activity_logs)
            cur.execute(
                """
                SELECT 
                    current_process as app_name,
                    timestamp,
                    total_seconds as duration_seconds,
                    timestamp::date as tracking_date
                FROM activity_log
                WHERE company_id = %s 
                  AND member_id = %s
                  AND timestamp >= %s 
                  AND timestamp <= %s
                  AND current_process IS NOT NULL
                ORDER BY timestamp
                """,
                (company_id, member_id, start_date, end_date)
            )
            app_logs = cur.fetchall()
            
            return jsonify({
                'success': True,
                'logs': app_logs
            }), 200
    
    except Exception as e:
        print(f"❌ Apps analytics error: {e}")
        return jsonify({'error': 'Failed to fetch app analytics'}), 500


# ============================================================================
# WEBSITE ANALYTICS
# ============================================================================

@analytics_bp.route('/analytics/websites', methods=['GET'])
@require_admin_auth
def get_websites_analytics():
    """Get detailed website usage analytics"""
    try:
        company_id = request.company_id
        member_id = request.args.get('member_id')
        start_date = request.args.get('start_date', (datetime.utcnow() - timedelta(days=7)).isoformat())
        end_date = request.args.get('end_date', datetime.utcnow().isoformat())
        
        if not member_id:
            return jsonify({'error': 'member_id is required'}), 400
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get raw website logs from browser_history JSONB - FIXED: activity_log (not activity_logs)
            cur.execute(
                """
                SELECT 
                    browser_history,
                    timestamp,
                    total_seconds as duration_seconds,
                    timestamp::date as tracking_date
                FROM activity_log
                WHERE company_id = %s 
                  AND member_id = %s
                  AND timestamp >= %s 
                  AND timestamp <= %s
                  AND browser_history IS NOT NULL
                ORDER BY timestamp
                """,
                (company_id, member_id, start_date, end_date)
            )
            website_logs = cur.fetchall()
            
            return jsonify({
                'success': True,
                'logs': website_logs
            }), 200
    
    except Exception as e:
        print(f"❌ Websites analytics error: {e}")
        return jsonify({'error': 'Failed to fetch website analytics'}), 500


# ============================================================================
# WORK BEHAVIOR ANALYTICS
# ============================================================================

@analytics_bp.route('/analytics/work-behavior', methods=['GET'])
@require_admin_auth
def get_work_behavior_analytics():
    """Get work behavior analytics combining attendance and activity data"""
    try:
        company_id = request.company_id
        member_id = request.args.get('member_id')
        date = request.args.get('date', datetime.utcnow().date().isoformat())
        
        if not member_id:
            return jsonify({'error': 'member_id is required'}), 400
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get attendance for the day
            cur.execute(
                """
                SELECT 
                    punch_in_time,
                    punch_out_time,
                    duration_minutes,
                    status
                FROM punch_logs
                WHERE company_id = %s 
                  AND member_id = %s
                  AND punch_date = %s
                ORDER BY punch_in_time DESC
                LIMIT 1
                """,
                (company_id, member_id, date)
            )
            attendance = cur.fetchone()
            
            # Get activity logs for the day - FIXED: activity_log (not activity_logs)
            cur.execute(
                """
                SELECT 
                    timestamp,
                    current_process as app_name,
                    is_idle,
                    locked,
                    total_seconds as duration_seconds
                FROM activity_log
                WHERE company_id = %s 
                  AND member_id = %s
                  AND DATE(timestamp) = %s
                ORDER BY timestamp
                """,
                (company_id, member_id, date)
            )
            activities = cur.fetchall()
            
            return jsonify({
                'success': True,
                'attendance': attendance,
                'activities': activities,
                'date': date
            }), 200
    
    except Exception as e:
        print(f"❌ Work behavior analytics error: {e}")
        return jsonify({'error': 'Failed to fetch work behavior analytics'}), 500
