from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, timedelta
import secrets

license_bp = Blueprint('license', __name__)

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(os.environ.get('DATABASE_URL'), cursor_factory=RealDictCursor)

@license_bp.route('/api/validate-license', methods=['POST'])
def validate_license():
    """Validate a license key and return company details"""
    try:
        data = request.get_json()
        license_key = data.get('license_key')
        
        if not license_key:
            return jsonify({'error': 'License key is required'}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if license exists and is active
        cur.execute("""
            SELECT company_id, company_name, license_key, max_employees, 
                   expiry_date, is_active, plan_type
            FROM companies
            WHERE license_key = %s
        """, (license_key,))
        
        company = cur.fetchone()
        cur.close()
        conn.close()
        
        if not company:
            return jsonify({'error': 'Invalid license key'}), 404
        
        if not company['is_active']:
            return jsonify({'error': 'License is inactive'}), 403
        
        # Check expiry
        if company['expiry_date'] and company['expiry_date'] < datetime.now().date():
            return jsonify({'error': 'License has expired'}), 403
        
        return jsonify({
            'valid': True,
            'company_id': company['company_id'],
            'company_name': company['company_name'],
            'max_employees': company['max_employees'],
            'expiry_date': company['expiry_date'].isoformat() if company['expiry_date'] else None,
            'plan_type': company['plan_type']
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@license_bp.route('/api/create-company', methods=['POST'])
def create_company():
    """Create a new company with license (admin only)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['company_name', 'admin_email', 'admin_password', 'max_employees', 'plan_type']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Generate unique license key
        license_key = f"WE-{secrets.token_hex(8).upper()}"
        
        # Calculate expiry date (1 year from now)
        expiry_date = datetime.now().date() + timedelta(days=365)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if company name already exists
        cur.execute("SELECT company_id FROM companies WHERE company_name = %s", (data['company_name'],))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Company name already exists'}), 409
        
        # Insert company
        cur.execute("""
            INSERT INTO companies (company_name, license_key, max_employees, expiry_date, plan_type, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            RETURNING company_id
        """, (data['company_name'], license_key, data['max_employees'], expiry_date, data['plan_type']))
        
        company_id = cur.fetchone()['company_id']
        
        # Create admin user
        hashed_password = generate_password_hash(data['admin_password'])
        
        cur.execute("""
            INSERT INTO members (company_id, email, username, password_hash, role, is_verified)
            VALUES (%s, %s, %s, %s, 'admin', TRUE)
            RETURNING username
        """, (company_id, data['admin_email'], data.get('admin_username', data['admin_email'].split('@')[0]), hashed_password))
        
        admin_username = cur.fetchone()['username']
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'message': 'Company created successfully',
            'company_id': company_id,
            'license_key': license_key,
            'admin_username': admin_username,
            'expiry_date': expiry_date.isoformat()
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@license_bp.route('/api/company/<int:company_id>/info', methods=['GET'])
def get_company_info(company_id):
    """Get company information"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT company_id, company_name, license_key, max_employees,
                   expiry_date, is_active, plan_type, created_at
            FROM companies
            WHERE company_id = %s
        """, (company_id,))
        
        company = cur.fetchone()
        
        if not company:
            cur.close()
            conn.close()
            return jsonify({'error': 'Company not found'}), 404
        
        # Get employee count
        cur.execute("""
            SELECT COUNT(*) as employee_count
            FROM members
            WHERE company_id = %s
        """, (company_id,))
        
        employee_count = cur.fetchone()['employee_count']
        
        cur.close()
        conn.close()
        
        return jsonify({
            'company_id': company['company_id'],
            'company_name': company['company_name'],
            'license_key': company['license_key'],
            'max_employees': company['max_employees'],
            'current_employees': employee_count,
            'expiry_date': company['expiry_date'].isoformat() if company['expiry_date'] else None,
            'is_active': company['is_active'],
            'plan_type': company['plan_type'],
            'created_at': company['created_at'].isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@license_bp.route('/api/company/<int:company_id>/deactivate', methods=['POST'])
def deactivate_company(company_id):
    """Deactivate a company license (admin only)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE companies
            SET is_active = FALSE
            WHERE company_id = %s
            RETURNING company_name
        """, (company_id,))
        
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return jsonify({'error': 'Company not found'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'message': f'Company {result["company_name"]} deactivated successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@license_bp.route('/api/company/<int:company_id>/extend', methods=['POST'])
def extend_license(company_id):
    """Extend company license expiry date"""
    try:
        data = request.get_json()
        days = data.get('days', 365)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE companies
            SET expiry_date = COALESCE(expiry_date, CURRENT_DATE) + INTERVAL '%s days'
            WHERE company_id = %s
            RETURNING company_name, expiry_date
        """, (days, company_id))
        
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return jsonify({'error': 'Company not found'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'message': f'License extended for {result["company_name"]}',
            'new_expiry_date': result['expiry_date'].isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
