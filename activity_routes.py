"""
ACTIVITY_ROUTES.PY - Activity Logs & Website Visits (Admin-Only)
=================================================================
✅ Secure company-scoped activity access
✅ Activity logs with filtering
✅ Website visits with time range
"""

from flask import Blueprint, request, jsonify
from admin_auth_routes import require_admin_auth
from db import get_db
from datetime import datetime, timedelta

activity_bp = Blueprint('activity', __name__)

# ============================================================================
# GET ACTIVITY LOGS FOR MEMBER
# ============================================================================

@activity_bp.route('/api/activity-logs/<int:member_id>', methods=['GET'])
@require_admin_auth
def get_member_activity_logs(member_id):
    """
    Get activity logs for a specific member
    
    Security:
    - Admin JWT required
    - Only activity logs for admin's company
    
    Query params:
    - date: Filter by date (YYYY-MM-DD), defaults to today IST
    - limit: Number of logs (default 50, max 500)
    - offset: Pagination offset (default 0)
    """
    try:
        company_id = request.company_id
        
        # Parse query parameters
        date_str = request.args.get('date')
        limit = min(int(request.args.get('limit', 50)), 500)
        offset = int(request.args.get('offset', 0))
        
        # Default to today IST if no date specified
        if date_str:
            try:
                filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            # Get current IST date
            from datetime import timezone
            ist_offset = timezone(timedelta(hours=5, minutes=30))
            ist_now = datetime.now(ist_offset)
            filter_date = ist_now.date()
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Verify member belongs to admin's company
            cur.execute(
                """
                SELECT id, name, email
                FROM members
                WHERE id = %s AND company_id = %s
                """,
                (member_id, company_id)
            )
            member = cur.fetchone()
            
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            
            # Get total count
            cur.execute(
                """
                SELECT COUNT(*) as total
                FROM activity_logs
                WHERE company_id = %s 
                  AND member_id = %s 
                  AND tracking_date = %s
                """,
                (company_id, member_id, filter_date)
            )
            total_count = cur.fetchone()['total']
            
            # Get activity logs
            cur.execute(
                """
                SELECT 
                    id,
                    timestamp,
                    window_title,
                    process_name,
                    app_name,
                    is_idle,
                    is_locked,
                    duration_seconds,
                    created_at
                FROM activity_logs
                WHERE company_id = %s 
                  AND member_id = %s 
                  AND tracking_date = %s
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
                """,
                (company_id, member_id, filter_date, limit, offset)
            )
            logs = cur.fetchall()
            
            return jsonify({
                'success': True,
                'member': {
                    'id': member['id'],
                    'name': member['name'],
                    'email': member['email']
                },
                'activities': logs,
                'pagination': {
                    'total': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': (offset + limit) < total_count
                },
                'date': filter_date.isoformat()
            }), 200
    
    except Exception as e:
        print(f"❌ Get activity logs error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch activity logs'}), 500


# ============================================================================
# GET WEBSITE VISITS FOR MEMBER
# ============================================================================

@activity_bp.route('/api/website-visits/<int:member_id>', methods=['GET'])
@require_admin_auth
def get_member_website_visits(member_id):
    """
    Get website visits for a specific member
    
    Security:
    - Admin JWT required
    - Only website visits for admin's company
    
    Query params:
    - start_date: Start date (YYYY-MM-DD) - defaults to today IST
    - end_date: End date (YYYY-MM-DD) - defaults to today IST
    - limit: Number of results (default 50, max 100)
    """
    try:
        company_id = request.company_id
        
        # Parse query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        limit = min(int(request.args.get('limit', 50)), 100)
        
        # Get current IST date
        from datetime import timezone
        ist_offset = timezone(timedelta(hours=5, minutes=30))
        ist_now = datetime.now(ist_offset)
        today_ist = ist_now.date()
        
        # Default to today IST if no date range specified
        if not start_date_str or not end_date_str:
            end_date = today_ist
            start_date = today_ist
        else:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Verify member belongs to admin's company
            cur.execute(
                """
                SELECT id, name, email
                FROM members
                WHERE id = %s AND company_id = %s
                """,
                (member_id, company_id)
            )
            member = cur.fetchone()
            
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            
            # Get website visits from browser history in activity_log
            cur.execute(
                """
                SELECT 
                    timestamp,
                    browser_history
                FROM activity_log
                WHERE company_id = %s 
                  AND member_id = %s 
                  AND tracking_date >= %s
                  AND tracking_date <= %s
                  AND browser_history IS NOT NULL
                  AND browser_history != '[]'
                ORDER BY timestamp DESC
                """,
                (company_id, member_id, start_date, end_date)
            )
            raw_data = cur.fetchall()
            
            # Parse and aggregate website visits
            import json
            from urllib.parse import urlparse
            
            website_stats = {}
            
            for row in raw_data:
                try:
                    browser_history = json.loads(row['browser_history'])
                    timestamp = row['timestamp']
                    
                    for url in browser_history:
                        if not url or url == 'N/A':
                            continue
                        
                        # Parse domain
                        try:
                            parsed = urlparse(url)
                            domain = parsed.netloc or parsed.path.split('/')[0]
                            
                            if domain not in website_stats:
                                website_stats[domain] = {
                                    'domain': domain,
                                    'url': url,
                                    'visit_count': 0,
                                    'first_visit': timestamp,
                                    'last_visit': timestamp,
                                    'urls': set(),
                                    'total_time_seconds': 0
                                }
                            
                            website_stats[domain]['visit_count'] += 1
                            website_stats[domain]['last_visit'] = max(
                                website_stats[domain]['last_visit'], 
                                timestamp
                            )
                            website_stats[domain]['first_visit'] = min(
                                website_stats[domain]['first_visit'], 
                                timestamp
                            )
                            website_stats[domain]['urls'].add(url)
                            # Estimate 5 seconds per visit
                            website_stats[domain]['total_time_seconds'] += 5
                        except Exception:
                            continue
                except Exception:
                    continue
            
            # Format results
            websites = []
            for domain, stats in sorted(
                website_stats.items(), 
                key=lambda x: x[1]['visit_count'], 
                reverse=True
            )[:limit]:
                websites.append({
                    'domain': stats['domain'],
                    'url': stats['url'],
                    'visit_count': stats['visit_count'],
                    'first_visit': stats['first_visit'].isoformat(),
                    'last_visit': stats['last_visit'].isoformat(),
                    'unique_urls': len(stats['urls']),
                    'total_time_seconds': stats['total_time_seconds']
                })
            
            return jsonify({
                'success': True,
                'member': {
                    'id': member['id'],
                    'name': member['name'],
                    'email': member['email']
                },
                'websites': websites,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }), 200
    
    except Exception as e:
        print(f"❌ Get website visits error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch website visits'}), 500


# ============================================================================
# GET APP USAGE FOR MEMBER
# ============================================================================

@activity_bp.route('/api/app-usage/<int:member_id>', methods=['GET'])
@require_admin_auth
def get_member_app_usage(member_id):
    """
    Get application usage statistics for a member
    
    Security:
    - Admin JWT required
    - Only app usage for admin's company
    
    Query params:
    - date: Filter by date (YYYY-MM-DD), defaults to today
    - limit: Number of apps (default 20, max 100)
    """
    try:
        company_id = request.company_id
        
        # Parse query parameters
        date_str = request.args.get('date')
        limit = min(int(request.args.get('limit', 20)), 100)
        
        # Default to today if no date specified
        if date_str:
            try:
                filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            filter_date = datetime.utcnow().date()
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Verify member belongs to admin's company
            cur.execute(
                """
                SELECT id, name, email
                FROM members
                WHERE id = %s AND company_id = %s
                """,
                (member_id, company_id)
            )
            member = cur.fetchone()
            
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            
            # Get app usage statistics
            cur.execute(
                """
                SELECT 
                    app_name,
                    COUNT(*) as usage_count,
                    SUM(CASE WHEN is_idle = FALSE AND is_locked = FALSE 
                        THEN duration_seconds ELSE 0 END) as active_seconds,
                    SUM(CASE WHEN is_idle = TRUE 
                        THEN duration_seconds ELSE 0 END) as idle_seconds,
                    SUM(duration_seconds) as total_seconds
                FROM activity_logs
                WHERE company_id = %s 
                  AND member_id = %s 
                  AND tracking_date = %s
                  AND app_name IS NOT NULL
                GROUP BY app_name
                ORDER BY total_seconds DESC
                LIMIT %s
                """,
                (company_id, member_id, filter_date, limit)
            )
            apps = cur.fetchall()
            
            # Format results
            result = []
            for app in apps:
                result.append({
                    'app_name': app['app_name'],
                    'usage_count': app['usage_count'],
                    'active_time_seconds': int(app['active_seconds'] or 0),
                    'idle_time_seconds': int(app['idle_seconds'] or 0),
                    'total_time_seconds': int(app['total_seconds'] or 0),
                    'active_time_formatted': f"{int(app['active_seconds'] or 0) // 3600}h {(int(app['active_seconds'] or 0) % 3600) // 60}m",
                    'total_time_formatted': f"{int(app['total_seconds'] or 0) // 3600}h {(int(app['total_seconds'] or 0) % 3600) // 60}m"
                })
            
            return jsonify({
                'success': True,
                'member': {
                    'id': member['id'],
                    'name': member['name'],
                    'email': member['email']
                },
                'apps': result,
                'date': filter_date.isoformat()
            }), 200
    
    except Exception as e:
        print(f"❌ Get app usage error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch app usage'}), 500


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['activity_bp']
