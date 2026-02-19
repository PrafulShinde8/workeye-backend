# WebSocket Connection Fix

## Issue
The frontend is trying to connect to `/ws` but Flask-SocketIO uses `/socket.io/` by default.

## Error in Logs
```
127.0.0.1 - - [21/Jan/2026:09:34:58 +0000] "GET /ws HTTP/1.1" 404 22
```

## Solution Options

### Option 1: Update Frontend (Recommended)
Change your frontend WebSocket connection from `/ws` to `/socket.io/`:

**If using socket.io-client:**
```javascript
import io from 'socket.io-client';

const socket = io('https://workeye-render-demo-backend.onrender.com', {
  path: '/socket.io/',  // This is the default Flask-SocketIO path
  transports: ['websocket', 'polling']
});
```

### Option 2: Configure Flask-SocketIO Custom Path
If you must use `/ws`, modify `app.py`:

```python
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    ping_timeout=20,
    ping_interval=10,
    path='/ws'  # Add this line
)
```

### Option 3: Disable WebSocket (if not needed)
If real-time updates aren't required, simply remove or comment out the WebSocket connection code in your frontend.

## Current Status
- ✅ **Fixed**: `activity_logs` → `activity_log` table name mismatch
- ⚠️ **Pending**: WebSocket path configuration needs frontend or backend update

## Related Files
- Backend: `app.py` (WebSocket configuration)
- Frontend: Check your WebSocket connection initialization code
