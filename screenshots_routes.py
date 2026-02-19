"""
SCREENSHOTS_ROUTES.PY - Screenshot Retrieval (Admin-Only)
==========================================================
✅ Secure company-scoped screenshot access
✅ Returns WebP screenshots with pagination
✅ Linked to member_id and admin_token
"""

from flask import Blueprint, request, jsonify, send_file
from admin_auth_routes import require_admin_auth
from db import get_db
from datetime import datetime, timedelta
from io import BytesIO
import os

screenshots_bp = Blueprint('screenshots', __name__)

# ============================================================================
# GET SCREENSHOTS FOR MEMBER
# ============================================================================

@screenshots_bp.route('/api/screenshots/<int:member_id>', methods=['GET'])
@require_admin_auth
def get_member_screenshots(member_id):
    """
    Get screenshots for a specific member
    
    Security:
    - Admin JWT required
    - Only screenshots for admin's company
    - No cross-company access
    
    Query params:
    - date: Filter by date (YYYY-MM-DD), defaults to today IST
    - limit: Number of screenshots (default 20, max 100)
    - offset: Pagination offset (default 0)
    """
    try:
        company_id = request.company_id  # From JWT
        
        # Parse query parameters
        date_str = request.args.get('date')
        limit = min(int(request.args.get('limit', 20)), 100)
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
                FROM screenshots
                WHERE company_id = %s 
                  AND member_id = %s 
                  AND tracking_date = %s
                """,
                (company_id, member_id, filter_date)
            )
            total_count = cur.fetchone()['total']
            
            # Get screenshots (metadata only, no binary data yet)
            cur.execute(
                """
                SELECT 
                    id,
                    timestamp,
                    tracking_date,
                    file_size,
                    width,
                    height,
                    is_valid,
                    invalid_reason,
                    is_saved_to_fs,
                    saved_filename,
                    created_at
                FROM screenshots
                WHERE company_id = %s 
                  AND member_id = %s 
                  AND tracking_date = %s
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
                """,
                (company_id, member_id, filter_date, limit, offset)
            )
            screenshots = cur.fetchall()
            
            # Format response
            result = []
            for screenshot in screenshots:
                result.append({
                    'id': screenshot['id'],
                    'timestamp': screenshot['timestamp'].isoformat(),
                    'tracking_date': screenshot['tracking_date'].isoformat(),
                    'file_size': screenshot['file_size'],
                    'width': screenshot['width'],
                    'height': screenshot['height'],
                    'is_valid': bool(screenshot.get('is_valid')),
                    'invalid_reason': screenshot.get('invalid_reason'),
                    'is_saved_to_fs': bool(screenshot.get('is_saved_to_fs')),
                    'saved_filename': screenshot.get('saved_filename'),
                    'name': member['name'],
                    'email': member['email']
                })

            # Return metadata list with pagination
            return jsonify({
                'screenshots': result,
                'pagination': {
                    'total': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': (offset + limit) < total_count
                }
            }), 200
    
    except Exception as e:
        print(f"❌ Get screenshots error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch screenshots'}), 500


# ============================================================================
# GET SINGLE SCREENSHOT IMAGE
# ============================================================================

@screenshots_bp.route('/api/screenshots/image/<int:screenshot_id>', methods=['GET'])
@require_admin_auth
def get_screenshot_image(screenshot_id):
    """
    Get actual screenshot image (WebP format)
    
    Security:
    - Admin JWT required
    - Verifies screenshot belongs to admin's company
    """
    try:
        company_id = request.company_id
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get screenshot with company verification
            cur.execute(
                """
                SELECT screenshot_data, timestamp
                FROM screenshots
                WHERE id = %s AND company_id = %s
                """,
                (screenshot_id, company_id)
            )
            screenshot = cur.fetchone()
            
            if not screenshot:
                return jsonify({'error': 'Screenshot not found'}), 404
            
            if not screenshot['screenshot_data']:
                return jsonify({'error': 'Screenshot data missing'}), 404
            
            # Return WebP image
            return send_file(
                BytesIO(screenshot['screenshot_data']),
                mimetype='image/webp',
                as_attachment=False,
                download_name=f"screenshot_{screenshot_id}_{screenshot['timestamp'].strftime('%Y%m%d_%H%M%S')}.webp"
            )
    
    except Exception as e:
        print(f"❌ Get screenshot image error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch screenshot image'}), 500


# ============================================================================
# BACKFILL (ADMIN)
# ============================================================================

@screenshots_bp.route('/api/screenshots/backfill', methods=['POST'])
@require_admin_auth
def backfill_screenshots():
    """Backfill recent screenshots to filesystem for admin (safe, limited window)"""
    try:
        data = request.get_json(silent=True) or {}
        days = int(data.get('days', 7))
        member_id = data.get('member_id')
        limit = int(data.get('limit', 500))

        cutoff = datetime.utcnow() - timedelta(days=days)
        saved = 0
        skipped = 0

        save_root = os.getenv('SCREENSHOT_SAVE_PATH', os.path.join(os.getcwd(), 'screenshots'))

        with get_db() as conn:
            cur = conn.cursor()
            params = [cutoff, limit]
            member_clause = ''
            if member_id:
                member_clause = 'AND member_id = %s'
                params.insert(0, member_id)

            query = f"""
                SELECT id, company_id, member_id, timestamp, screenshot_data
                FROM screenshots
                WHERE screenshot_data IS NOT NULL AND (is_saved_to_fs IS DISTINCT FROM TRUE OR saved_filename IS NULL)
                  AND timestamp >= %s
            """
            if member_clause:
                # Place member filter correctly
                query = query.replace('AND timestamp >= %s', f'AND member_id = %s\n                  AND timestamp >= %s')

            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            for r in rows:
                sid = r['id']
                cid = r['company_id']
                mid = r['member_id']
                ts = r['timestamp']
                data_blob = r['screenshot_data']

                try:
                    ts_str = ts.strftime('%Y%m%d_%H%M%S')
                except Exception:
                    ts_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

                fname = f"screenshot_{sid}_{ts_str}.webp"
                fpath = os.path.join(save_root, str(cid), str(mid), fname)

                if os.path.exists(fpath):
                    skipped += 1
                    try:
                        cur.execute("UPDATE screenshots SET is_saved_to_fs = TRUE, saved_filename = %s WHERE id = %s", (fpath, sid))
                        conn.commit()
                    except Exception:
                        pass
                    continue

                try:
                    os.makedirs(os.path.dirname(fpath), exist_ok=True)
                    with open(fpath, 'wb') as fp:
                        fp.write(data_blob)
                    cur.execute("UPDATE screenshots SET is_saved_to_fs = TRUE, saved_filename = %s WHERE id = %s", (fpath, sid))
                    conn.commit()
                    saved += 1
                except Exception as e:
                    print(f"⚠️ Backfill failed for {sid}: {e}")

        return jsonify({'success': True, 'saved': saved, 'skipped': skipped, 'message': f'Processed up to {limit} screenshots from last {days} days.'}), 200
    except Exception as e:
        print(f"❌ Backfill error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to backfill screenshots', 'details': str(e)}), 500


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['screenshots_bp']
