"""
MEMBERS_ROUTES.PY - SAFE VERSION (Handles both name and full_name)
===================================================================
✅ Tries full_name first, falls back to name
✅ Works with ANY database schema
✅ Minimal changes from original
✅ All admin functionality preserved
"""

from flask import Blueprint, request, jsonify
from admin_auth_routes import require_admin_auth
from db import get_db

members_bp = Blueprint('members', __name__)

# ============================================================================
# CREATE MEMBER (Admin invites employee)
# ============================================================================

@members_bp.route('/admin/members', methods=['POST'])
@require_admin_auth
def create_member():
    """
    Admin creates/invites a member (employee)
    
    Security:
    - Admin JWT required (has company_id)
    - Member created ONLY for admin's company
    - NO password for member
    """
    try:
        data = request.get_json()
        company_id = request.company_id  # From JWT
        admin_id = request.admin_id
        
        # Validate required fields
        email = data.get('email', '').lower().strip()
        name = data.get('name', '').strip()
        
        if not email or not name:
            return jsonify({'error': 'Email and name are required'}), 400
        
        position = data.get('position', '')
        department = data.get('department', '')
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Check if member already exists in THIS company
            cur.execute(
                """
                SELECT id FROM members
                WHERE company_id = %s AND email = %s
                """,
                (company_id, email)
            )
            if cur.fetchone():
                return jsonify({'error': 'Member already exists in your company'}), 409
            
            # SAFE: Try to detect which column exists by checking table structure
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'members' 
                AND column_name IN ('name', 'full_name')
            """)
            columns = [row['column_name'] for row in cur.fetchall()]
            
            # Determine which column to use
            if 'full_name' in columns:
                name_column = 'full_name'
            elif 'name' in columns:
                name_column = 'name'
            else:
                return jsonify({'error': 'Database schema error: no name column found'}), 500
            
            print(f"✅ Using column: {name_column}")
            
            # Create member with correct column
            query = f"""
                INSERT INTO members (
                    company_id, email, {name_column}, position, department,
                    is_active, created_by_admin_id
                )
                VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                RETURNING id, email, {name_column} as name, position, department, created_at
            """
            
            cur.execute(query, (company_id, email, name, position, department, admin_id))
            member = cur.fetchone()
            
            return jsonify({
                'success': True,
                'member': member
            }), 201
    
    except Exception as e:
        print(f"❌ Create member error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to create member'}), 500


# ============================================================================
# GET ALL MEMBERS (Company-scoped) - SAFE VERSION
# ============================================================================

@members_bp.route('/admin/members', methods=['GET'])
@require_admin_auth
def get_members():
    """
    Get all members for admin's company ONLY
    
    Security:
    - Automatically filtered by company_id from JWT
    - Admin can ONLY see their company's members
    
    SAFE: Detects which column exists (name or full_name)
    """
    try:
        company_id = request.company_id  # From JWT
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # SAFE: Detect which column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'members' 
                AND column_name IN ('name', 'full_name')
            """)
            columns = [row['column_name'] for row in cur.fetchall()]
            
            # Determine which column to use
            if 'full_name' in columns:
                name_column = 'full_name'
            elif 'name' in columns:
                name_column = 'name'
            else:
                return jsonify({'error': 'Database schema error'}), 500
            
            print(f"✅ GET members using column: {name_column}")
            
            # CRITICAL: Filter by company_id with correct column
            query = f"""
                SELECT
                    m.id,
                    m.email,
                    m.{name_column} as name,
                    m.position,
                    m.department,
                    m.is_active,
                    m.last_activity_at,
                    m.created_at,
                    COUNT(d.id) as device_count
                FROM members m
                LEFT JOIN devices d ON d.member_id = m.id AND d.company_id = %s
                WHERE m.company_id = %s
                GROUP BY m.id, m.email, m.{name_column}, m.position, m.department, 
                         m.is_active, m.last_activity_at, m.created_at
                ORDER BY m.created_at DESC
            """
            
            cur.execute(query, (company_id, company_id))
            members = cur.fetchall()
            
            print(f"✅ Found {len(members)} members")
            
            return jsonify({
                'success': True,
                'members': members
            }), 200
    
    except Exception as e:
        print(f"❌ Get members error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch members'}), 500


# ============================================================================
# GET SINGLE MEMBER (Company-scoped) - SAFE VERSION
# ============================================================================

@members_bp.route('/admin/members/<int:member_id>', methods=['GET'])
@require_admin_auth
def get_member(member_id):
    """
    Get member details (company-scoped)
    
    Security:
    - Member must belong to admin's company
    """
    try:
        company_id = request.company_id
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # SAFE: Detect column
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'members' 
                AND column_name IN ('name', 'full_name')
            """)
            columns = [row['column_name'] for row in cur.fetchall()]
            
            if 'full_name' in columns:
                name_column = 'full_name'
            elif 'name' in columns:
                name_column = 'name'
            else:
                return jsonify({'error': 'Database schema error'}), 500
            
            # CRITICAL: Filter by company_id AND member_id
            query = f"""
                SELECT
                    m.id,
                    m.email,
                    m.{name_column} as name,
                    m.position,
                    m.department,
                    m.is_active,
                    m.last_activity_at,
                    m.created_at
                FROM members m
                WHERE m.company_id = %s AND m.id = %s
            """
            
            cur.execute(query, (company_id, member_id))
            member = cur.fetchone()
            
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            
            # Get member's devices
            cur.execute(
                """
                SELECT id, device_id, device_name, hostname, status, last_seen
                FROM devices
                WHERE company_id = %s AND member_id = %s
                """,
                (company_id, member_id)
            )
            devices = cur.fetchall()
            
            return jsonify({
                'success': True,
                'member': member,
                'devices': devices
            }), 200
    
    except Exception as e:
        print(f"❌ Get member error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch member'}), 500


# ============================================================================
# UPDATE MEMBER (Company-scoped) - SAFE VERSION
# ============================================================================

@members_bp.route('/admin/members/<int:member_id>', methods=['PUT'])
@require_admin_auth
def update_member(member_id):
    """
    Update member details (company-scoped)
    
    Security:
    - Member must belong to admin's company
    """
    try:
        data = request.get_json()
        company_id = request.company_id
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # SAFE: Detect column
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'members' 
                AND column_name IN ('name', 'full_name')
            """)
            columns = [row['column_name'] for row in cur.fetchall()]
            
            if 'full_name' in columns:
                name_column = 'full_name'
            elif 'name' in columns:
                name_column = 'name'
            else:
                return jsonify({'error': 'Database schema error'}), 500
            
            # Build dynamic UPDATE
            update_fields = []
            params = []
            
            if 'name' in data:
                update_fields.append(f"{name_column} = %s")
                params.append(data['name'])
            if 'position' in data:
                update_fields.append("position = %s")
                params.append(data['position'])
            if 'department' in data:
                update_fields.append("department = %s")
                params.append(data['department'])
            if 'is_active' in data:
                update_fields.append("is_active = %s")
                params.append(data['is_active'])
            
            if not update_fields:
                return jsonify({'error': 'No fields to update'}), 400
            
            params.extend([company_id, member_id])
            
            # CRITICAL: WHERE company_id = %s AND member_id = %s
            query = f"""
                UPDATE members
                SET {', '.join(update_fields)}
                WHERE company_id = %s AND id = %s
                RETURNING id, email, {name_column} as name, position, department, is_active
            """
            
            cur.execute(query, params)
            member = cur.fetchone()
            
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            
            return jsonify({
                'success': True,
                'member': member
            }), 200
    
    except Exception as e:
        print(f"❌ Update member error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to update member'}), 500


# ============================================================================
# DELETE MEMBER (Company-scoped)
# ============================================================================

@members_bp.route('/admin/members/<int:member_id>', methods=['DELETE'])
@require_admin_auth
def delete_member(member_id):
    """
    Delete member (company-scoped)
    
    Security:
    - Member must belong to admin's company
    - Cascades to devices, activity_logs, etc.
    """
    try:
        company_id = request.company_id
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # CRITICAL: WHERE company_id = %s AND id = %s
            cur.execute(
                """
                DELETE FROM members
                WHERE company_id = %s AND id = %s
                """,
                (company_id, member_id)
            )
            
            if cur.rowcount == 0:
                return jsonify({'error': 'Member not found'}), 404
            
            return jsonify({
                'success': True,
                'message': 'Member deleted successfully'
            }), 200
    
    except Exception as e:
        print(f"❌ Delete member error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to delete member'}), 500


# ============================================================================
# DOWNLOAD TRACKER WITH EMBEDDED TOKEN (Company-scoped)
# ============================================================================

@members_bp.route('/admin/download-tracker', methods=['GET'])
@require_admin_auth
def download_tracker():
    """
    Generate and serve tracker file with embedded company token
    
    Security:
    - Admin JWT required (contains company_id)
    - Tracker token is fetched from company record
    - Token is embedded in the tracker configuration
    - Each company gets their own token-embedded tracker
    
    NEW FEATURE: Allows admin to download tracker pre-configured for their company
    """
    try:
        company_id = request.company_id  # From JWT
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Get company's tracker token
            cur.execute(
                """
                SELECT tracker_token, company_name, company_username
                FROM companies
                WHERE id = %s AND is_active = TRUE
                """,
                (company_id,)
            )
            company = cur.fetchone()
            
            if not company:
                return jsonify({'error': 'Company not found or inactive'}), 404
            
            tracker_token = company['tracker_token']
            company_name = company['company_name']
            
            if not tracker_token:
                return jsonify({'error': 'Tracker token not found for company'}), 500
            
            # Read the original tracker file
            import os
            tracker_path = os.path.join(os.path.dirname(__file__), 'tracker', 'wkv0.0.py')
            
            if not os.path.exists(tracker_path):
                return jsonify({'error': 'Tracker file not found'}), 500
            
            with open(tracker_path, 'r', encoding='utf-8') as f:
                tracker_code = f.read()
            
            # Embed the tracker token in the configuration
            # Replace the tracker_token line in CONFIG dict
            modified_code = tracker_code.replace(
                "'tracker_token': None,",
                f"'tracker_token': '{tracker_token}',"
            )
            
            # Also update the company_id if needed
            modified_code = modified_code.replace(
                "'company_id': None,",
                f"'company_id': {company_id},"
            )
            
            # Create a temporary file with the modified code
            from flask import send_file
            from io import BytesIO
            
            # Convert to bytes for download
            tracker_bytes = BytesIO(modified_code.encode('utf-8'))
            tracker_bytes.seek(0)
            
            # Generate filename with company name
            safe_company_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"WorkEye-Tracker-{safe_company_name}.py"
            
            print(f"✅ Generated tracker for company_id={company_id}, token embedded")
            
            return send_file(
                tracker_bytes,
                mimetype='text/x-python',
                as_attachment=True,
                download_name=filename
            )
    
    except Exception as e:
        print(f"❌ Download tracker error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to generate tracker'}), 500


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['members_bp']
