"""
WEBSOCKET_SERVER.PY - Multi-Tenant Real-Time Updates
======================================================
✅ Multi-tenant isolation (clients grouped by company_id)
✅ JWT authentication for WebSocket connections
✅ Automatic heartbeat and connection health monitoring
✅ Scalable connection management
✅ Broadcast updates only to same tenant
"""

import asyncio
import json
import jwt
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, Set
import websockets
from websockets.server import WebSocketServerProtocol
from datetime import timezone, timedelta

# ============================================================================
# CONFIGURATION
# ============================================================================

JWT_SECRET = os.environ.get('JWT_SECRET', 'your-super-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
HEARTBEAT_INTERVAL = 30  # seconds
CONNECTION_TIMEOUT = 60  # seconds

# Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))
# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

class ConnectionManager:
    """
    Manages WebSocket connections with multi-tenant isolation
    Each company has its own set of connections
    """
    
    def __init__(self):
        # company_id -> Set of websockets
        self.company_connections: Dict[int, Set[WebSocketServerProtocol]] = defaultdict(set)
        
        # websocket -> {company_id, user_id, email, last_ping}
        self.connection_metadata: Dict[WebSocketServerProtocol, dict] = {}
    
    async def connect(self, websocket: WebSocketServerProtocol, company_id: int, user_id: int, email: str):
        """Register new WebSocket connection for a tenant"""
        self.company_connections[company_id].add(websocket)
        self.connection_metadata[websocket] = {
            'company_id': company_id,
            'user_id': user_id,
            'email': email,
            # 'connected_at': datetime.utcnow(),
            # 'last_ping': datetime.utcnow()
            'connected_at': datetime.now(IST),
            'last_ping': datetime.now(IST),
        }
        print(f"✅ Connected: company_id={company_id}, user_id={user_id}, total={len(self.company_connections[company_id])}")
    
    def disconnect(self, websocket: WebSocketServerProtocol):
        """Remove WebSocket connection"""
        if websocket in self.connection_metadata:
            metadata = self.connection_metadata[websocket]
            company_id = metadata['company_id']
            user_id = metadata['user_id']
            
            self.company_connections[company_id].discard(websocket)
            del self.connection_metadata[websocket]
            
            # Clean up empty company sets
            if not self.company_connections[company_id]:
                del self.company_connections[company_id]
            
            print(f"🔌 Disconnected: company_id={company_id}, user_id={user_id}")
    
    async def broadcast_to_company(self, company_id: int, message: dict, exclude_ws=None):
        """
        Broadcast message to all connections in a company (tenant)
        MULTI-TENANT: Only sends to connections with matching company_id
        """
        if company_id not in self.company_connections:
            return
        
        connections = self.company_connections[company_id].copy()
        if exclude_ws:
            connections.discard(exclude_ws)
        
        if connections:
            message_json = json.dumps(message)
            await asyncio.gather(
                *[ws.send(message_json) for ws in connections],
                return_exceptions=True
            )
    
    async def send_to_user(self, company_id: int, user_id: int, message: dict):
        """Send message to specific user within a tenant"""
        if company_id not in self.company_connections:
            return
        
        message_json = json.dumps(message)
        for ws in self.company_connections[company_id]:
            metadata = self.connection_metadata.get(ws)
            if metadata and metadata['user_id'] == user_id:
                try:
                    await ws.send(message_json)
                except Exception as e:
                    print(f"❌ Error sending to user {user_id}: {e}")
    
    def get_company_connection_count(self, company_id: int) -> int:
        """Get number of active connections for a company"""
        return len(self.company_connections.get(company_id, set()))
    
    def update_ping(self, websocket: WebSocketServerProtocol):
        """Update last ping time for connection health"""
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]['last_ping'] = datetime.utcnow()

# Global connection manager
manager = ConnectionManager()

# ============================================================================
# WEBSOCKET HANDLERS
# ============================================================================

async def authenticate_websocket(token: str) -> dict:
    """
    Authenticate WebSocket connection using JWT
    Returns payload with user_id and company_id
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            'authenticated': True,
            'user_id': payload.get('admin_id') or payload.get('user_id'),
            'company_id': payload.get('company_id') or payload.get('tenant_id'),
            'email': payload.get('email')
        }
    except jwt.ExpiredSignatureError:
        return {'authenticated': False, 'error': 'Token expired'}
    except jwt.InvalidTokenError:
        return {'authenticated': False, 'error': 'Invalid token'}

async def handle_client_message(websocket: WebSocketServerProtocol, message: dict):
    """
    Handle incoming messages from client
    All broadcasts are tenant-isolated
    """
    message_type = message.get('type')
    metadata = manager.connection_metadata.get(websocket)
    
    if not metadata:
        return
    
    company_id = metadata['company_id']
    user_id = metadata['user_id']
    
    if message_type == 'ping':
        # Heartbeat - update last ping time
        manager.update_ping(websocket)
        await websocket.send(json.dumps({'type': 'pong', 'timestamp': datetime.utcnow().isoformat()}))
    
    elif message_type == 'member_status_update':
        # Broadcast status update to all company members
        await manager.broadcast_to_company(company_id, {
            'type': 'member_status_change',
            'user_id': user_id,
            'status': message.get('status'),
            'timestamp': datetime.utcnow().isoformat()
        }, exclude_ws=websocket)
    
    elif message_type == 'activity_update':
        # Broadcast activity update to company
        await manager.broadcast_to_company(company_id, {
            'type': 'activity_update',
            'user_id': user_id,
            'data': message.get('data'),
            'timestamp': datetime.utcnow().isoformat()
        })
    
    elif message_type == 'screenshot_captured':
        # Notify company of new screenshot
        await manager.broadcast_to_company(company_id, {
            'type': 'screenshot_captured',
            'member_id': message.get('member_id'),
            'timestamp': datetime.utcnow().isoformat()
        })
    
    elif message_type == 'punch_in' or message_type == 'punch_out':
        # Notify company of punch in/out
        await manager.broadcast_to_company(company_id, {
            'type': message_type,
            'member_id': message.get('member_id'),
            'timestamp': message.get('timestamp') or datetime.utcnow().isoformat()
        })

# async def websocket_handler(websocket: WebSocketServerProtocol):
#     """
#     Main WebSocket connection handler
#     Handles authentication, message routing, and connection lifecycle
#     """
#     authenticated = False
#     company_id = None
#     user_id = None
    
#     try:
#         # Wait for authentication message
#         auth_message = await asyncio.wait_for(websocket.recv(), timeout=10)
#         auth_data = json.loads(auth_message)
        
#         if auth_data.get('type') != 'authenticate':
#             await websocket.send(json.dumps({'error': 'Authentication required'}))
#             return
        
#         token = auth_data.get('token')
#         if not token:
#             await websocket.send(json.dumps({'error': 'Token required'}))
#             return
        
#         # Authenticate
#         auth_result = await authenticate_websocket(token)
        
#         if not auth_result.get('authenticated'):
#             await websocket.send(json.dumps({'error': auth_result.get('error', 'Authentication failed')}))
#             return
        
#         # Extract tenant info
#         company_id = auth_result['company_id']
#         user_id = auth_result['user_id']
#         email = auth_result['email']
        
#         # Register connection
#         await manager.connect(websocket, company_id, user_id, email)
#         authenticated = True
        
#         # Send authentication success
#         await websocket.send(json.dumps({
#             'type': 'authenticated',
#             'company_id': company_id,
#             'user_id': user_id,
#             'timestamp': datetime.utcnow().isoformat()
#         }))
        
#         # Message loop
#         async for message_str in websocket:
#             try:
#                 message = json.loads(message_str)
#                 await handle_client_message(websocket, message)
#             except json.JSONDecodeError:
#                 await websocket.send(json.dumps({'error': 'Invalid JSON'}))
#             except Exception as e:
#                 print(f"❌ Message handling error: {e}")
#                 await websocket.send(json.dumps({'error': 'Message processing failed'}))
    
#     except asyncio.TimeoutError:
#         print("❌ Authentication timeout")
#     except websockets.exceptions.ConnectionClosed:
#         print(f"🔌 Connection closed: company_id={company_id}")
#     except Exception as e:
#         print(f"❌ WebSocket error: {e}")
#         import traceback
#         traceback.print_exc()
#     finally:
#         if authenticated:
#             manager.disconnect(websocket)


async def websocket_handler(websocket: WebSocketServerProtocol):
    authenticated = False
    company_id = None
    user_id = None

    try:
        auth_message = await asyncio.wait_for(websocket.recv(), timeout=10)
        auth_data = json.loads(auth_message)

        if auth_data.get("type") != "authenticate":
            await websocket.send(json.dumps({"error": "Authentication required"}))
            return

        token = auth_data.get("token")
        if not token:
            await websocket.send(json.dumps({"error": "Token required"}))
            return

        auth_result = await authenticate_websocket(token)

        if not auth_result.get("authenticated"):
            await websocket.send(json.dumps({"error": auth_result["error"]}))
            return

        company_id = auth_result["company_id"]
        user_id = auth_result["user_id"]
        email = auth_result["email"]

        await manager.connect(websocket, company_id, user_id, email)
        authenticated = True

        await websocket.send(json.dumps({
            "type": "authenticated",
            "company_id": company_id,
            "user_id": user_id
        }))

        async for message_str in websocket:
            message = json.loads(message_str)
            await handle_client_message(websocket, message)

    except Exception as e:
        print("WebSocket error:", e)

    finally:
        if authenticated:
            manager.disconnect(websocket)


# ============================================================================
# HEARTBEAT MONITOR
# ============================================================================

async def heartbeat_monitor():
    """
    Monitor connection health and remove stale connections
    Runs every HEARTBEAT_INTERVAL seconds
    """
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        
        # now = datetime.utcnow()
        now = datetime.now(IST)
        stale_connections = []
        
        for ws, metadata in manager.connection_metadata.items():
            last_ping = metadata.get('last_ping')
            if last_ping and (now - last_ping).seconds > CONNECTION_TIMEOUT:
                stale_connections.append(ws)
        
        # Remove stale connections
        for ws in stale_connections:
            try:
                await ws.close()
            except:
                pass
            manager.disconnect(ws)
        
        if stale_connections:
            print(f"🧹 Cleaned up {len(stale_connections)} stale connections")

# ============================================================================
# SERVER STARTUP
# ============================================================================

async def start_websocket_server(host='0.0.0.0', port=8765):
    """
    Start WebSocket server with heartbeat monitoring
    """
    # Start heartbeat monitor
    asyncio.create_task(heartbeat_monitor())
    
    # Start WebSocket server
    async with websockets.serve(websocket_handler, host, port):
        print(f"🔌 WebSocket server started on ws://{host}:{port}")
        print(f"✅ Multi-tenant isolation enabled")
        print(f"✅ JWT authentication required")
        await asyncio.Future()  # Run forever

if __name__ == '__main__':
    # Run server
    asyncio.run(start_websocket_server())
