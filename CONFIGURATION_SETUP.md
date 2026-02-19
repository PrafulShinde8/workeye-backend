# Configuration System - Complete Setup

## 📊 Overview
Complete configuration management system for WorkEye that allows admins to control:
- Screenshot capture intervals
- Idle timeout thresholds
- Office working hours
- Working days

## 🏛️ Database Schema

### Table: `company_configurations`
```sql
CREATE TABLE IF NOT EXISTS company_configurations (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    screenshot_interval_minutes INTEGER DEFAULT 10,
    idle_timeout_minutes INTEGER DEFAULT 5,
    office_start_time TIME DEFAULT '09:00:00',
    office_end_time TIME DEFAULT '18:00:00',
    working_days INTEGER[] DEFAULT ARRAY[1,2,3,4,5],
    last_modified_by VARCHAR(255),
    last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id)
);
```

**Note:** Table is auto-created on first GET request if it doesn't exist.

## 🔑 API Endpoints

### 1. Get Configuration (Admin)
```http
GET /api/configuration
Authorization: Bearer <admin_jwt_token>
```

**Response:**
```json
{
  "success": true,
  "config": {
    "id": 1,
    "company_id": 5,
    "screenshot_interval_minutes": 10,
    "idle_timeout_minutes": 5,
    "office_start_time": "09:00:00",
    "office_end_time": "18:00:00",
    "working_days": [1, 2, 3, 4, 5],
    "last_modified_by": "admin@company.com",
    "last_modified_at": "2026-01-19T12:00:00",
    "created_at": "2026-01-15T10:00:00"
  }
}
```

### 2. Update Configuration (Admin)
```http
POST /api/configuration
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json

{
  "company_id": 5,
  "config": {
    "screenshot_interval_minutes": 15,
    "idle_timeout_minutes": 10,
    "office_start_time": "09:00:00",
    "office_end_time": "18:00:00",
    "working_days": [1, 2, 3, 4, 5]
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Configuration updated successfully",
  "config_id": 1,
  "updated_at": "2026-01-19T12:00:00",
  "created_at": "2026-01-15T10:00:00"
}
```

### 3. Get Tracker Configuration (Tracker Client)
```http
GET /api/tracker/configuration
X-Tracker-Token: <tracker_token>
```

**Response:**
```json
{
  "success": true,
  "screenshot_interval_minutes": 15,
  "idle_timeout_minutes": 10
}
```

## 💻 Frontend Implementation

### File: `src/components/Configuration.tsx`

**Features:**
- ✅ Modest, responsive UI
- ✅ Real-time configuration display
- ✅ Shows all configuration fields:
  - ID
  - Company ID
  - Screenshot interval
  - Idle timeout
  - Office hours
  - Working days
  - Last modified by
  - Last modified at
  - Created at
- ✅ Input validation
- ✅ Error handling
- ✅ Success notifications
- ✅ Mobile responsive design

**Key Components:**
1. **Current Settings Display** - Shows active configuration in colored cards
2. **Metadata Section** - Displays modification history
3. **Edit Form** - Clean form with validation
4. **Info Box** - Explains tracker synchronization

## 🔧 Backend Implementation

### File: `configuration_routes.py`

**Features:**
- ✅ Auto-creates table if missing
- ✅ Auto-creates default config for new companies
- ✅ Validates input ranges:
  - Screenshot interval: 1-60 minutes
  - Idle timeout: 1-30 minutes
  - Working days: must be non-empty array
- ✅ Tracks modification history
- ✅ Multi-tenant isolation (company_id based)
- ✅ Admin authentication required
- ✅ Tracker endpoint (no auth, uses tracker token)

**Blueprint Registration:**
```python
# In app.py
from configuration_routes import configuration_bp
app.register_blueprint(configuration_bp)
```

## 🚀 Tracker Integration (Next Step)

For `wkv0.0.py` to use dynamic configuration:

```python
import requests
import time

# Tracker configuration sync
class ConfigurationManager:
    def __init__(self, tracker_token, api_url):
        self.tracker_token = tracker_token
        self.api_url = api_url
        self.screenshot_interval = 10  # Default
        self.idle_timeout = 5  # Default
        self.last_sync = 0
        self.sync_interval = 300  # Re-sync every 5 minutes
    
    def fetch_configuration(self):
        """Fetch configuration from server"""
        try:
            response = requests.get(
                f"{self.api_url}/api/tracker/configuration",
                headers={'X-Tracker-Token': self.tracker_token},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.screenshot_interval = data.get('screenshot_interval_minutes', 10)
                    self.idle_timeout = data.get('idle_timeout_minutes', 5)
                    self.last_sync = time.time()
                    print(f"✅ Config synced: screenshot={self.screenshot_interval}min, idle={self.idle_timeout}min")
                    return True
        except Exception as e:
            print(f"⚠️ Config fetch failed: {e}")
        
        return False
    
    def should_sync(self):
        """Check if it's time to re-sync configuration"""
        return (time.time() - self.last_sync) > self.sync_interval
    
    def get_screenshot_interval(self):
        """Get screenshot interval in seconds"""
        if self.should_sync():
            self.fetch_configuration()
        return self.screenshot_interval * 60
    
    def get_idle_timeout(self):
        """Get idle timeout in seconds"""
        if self.should_sync():
            self.fetch_configuration()
        return self.idle_timeout * 60

# Usage in tracker:
config_manager = ConfigurationManager(TRACKER_TOKEN, API_URL)
config_manager.fetch_configuration()  # Initial fetch

# In main loop:
screenshot_interval = config_manager.get_screenshot_interval()
idle_timeout = config_manager.get_idle_timeout()
```

## 🎯 Validation Rules

### Screenshot Interval
- **Range:** 1-60 minutes
- **Default:** 10 minutes
- **Purpose:** How often screenshots are captured

### Idle Timeout
- **Range:** 1-30 minutes
- **Default:** 5 minutes
- **Purpose:** Time before marking user as idle

### Office Hours
- **Format:** HH:MM:SS (24-hour)
- **Default:** 09:00:00 - 18:00:00

### Working Days
- **Format:** Array of integers
- **Values:** 0=Sunday, 1=Monday, ..., 6=Saturday
- **Default:** [1, 2, 3, 4, 5] (Monday-Friday)
- **Validation:** Must be non-empty array

## 🔒 Security

1. **Admin Endpoints:** Require JWT authentication via `@require_admin_auth`
2. **Tracker Endpoint:** Uses tracker token validation
3. **Multi-tenant Isolation:** All queries scoped to company_id
4. **Input Validation:** Range checks on all numeric inputs
5. **SQL Injection Prevention:** Parameterized queries

## 📊 Data Flow

```
Admin Dashboard (/configuration)
    ↓
    POST /api/configuration
    ↓
Backend (configuration_routes.py)
    ↓
Database (company_configurations table)
    ↓
GET /api/tracker/configuration
    ↓
Tracker (wkv0.0.py)
    ↓
Applies settings:
- Screenshot interval
- Idle timeout
```

## 🛠️ Testing

### 1. Test Configuration GET
```bash
curl -X GET "https://your-backend.com/api/configuration" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 2. Test Configuration UPDATE
```bash
curl -X POST "https://your-backend.com/api/configuration" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": 5,
    "config": {
      "screenshot_interval_minutes": 15,
      "idle_timeout_minutes": 10,
      "office_start_time": "09:00:00",
      "office_end_time": "18:00:00",
      "working_days": [1,2,3,4,5]
    }
  }'
```

### 3. Test Tracker Configuration
```bash
curl -X GET "https://your-backend.com/api/tracker/configuration" \
  -H "X-Tracker-Token: YOUR_TRACKER_TOKEN"
```

## ✅ Checklist

### Backend
- [x] Create `configuration_routes.py`
- [x] Register blueprint in `app.py`
- [x] Auto-create table on first request
- [x] GET endpoint for admin
- [x] POST endpoint for admin
- [x] GET endpoint for tracker
- [x] Input validation
- [x] Multi-tenant isolation

### Frontend
- [x] Update `Configuration.tsx`
- [x] Modest, responsive UI
- [x] Display all configuration fields
- [x] Show metadata (id, company_id, timestamps)
- [x] Input validation
- [x] Error handling
- [x] Success notifications

### Integration
- [ ] Update `wkv0.0.py` to fetch config from server
- [ ] Implement ConfigurationManager class in tracker
- [ ] Test tracker with dynamic configuration
- [ ] Verify tracker re-syncs every 5 minutes

## 📝 Notes

1. **Default Configuration:** Created automatically for new companies
2. **Tracker Sync:** Trackers should re-fetch config every 5 minutes
3. **Immediate Effect:** Changes apply immediately to new tracker sessions
4. **Graceful Degradation:** If config fetch fails, tracker uses last known values or defaults
5. **Company Isolation:** Each company has independent configuration

## 🔗 Related Files

- Backend:
  - `configuration_routes.py` - Configuration API endpoints
  - `app.py` - Blueprint registration
  - `admin_auth_routes.py` - Admin authentication decorator
  
- Frontend:
  - `src/components/Configuration.tsx` - Configuration UI
  - `src/contexts/AuthContext.tsx` - Authentication context

- Tracker:
  - `wkv0.0.py` - Tracker client (needs update for dynamic config)

---

**Version:** 1.0  
**Last Updated:** 2026-01-19  
**Author:** WorkEye Development Team
