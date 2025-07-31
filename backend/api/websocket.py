import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from core.database import db_manager
from core.security import SecurityManager
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
websocket_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[int, List[str]] = {}

    async def connect(self, websocket: WebSocket, connection_id: str, user_id: int):
        await websocket.accept()
        self.active_connections[connection_id] = websocket

        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(connection_id)

        logger.info(f"WebSocket connected: {connection_id} for user {user_id}")

    def disconnect(self, connection_id: str, user_id: int):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        if user_id in self.user_connections:
            self.user_connections[user_id] = [
                conn for conn in self.user_connections[user_id] if conn != connection_id
            ]
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        logger.info(f"WebSocket disconnected: {connection_id}")

    async def send_personal_message(self, message: dict, connection_id: str):
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message to {connection_id}: {e}")
                await self.force_disconnect(connection_id)

    async def send_to_user(self, message: dict, user_id: int):
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id]:
                await self.send_personal_message(message, connection_id)

    async def force_disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            try:
                await self.active_connections[connection_id].close()
            except:
                pass

            # Find user_id for cleanup
            user_id = None
            for uid, connections in self.user_connections.items():
                if connection_id in connections:
                    user_id = uid
                    break

            if user_id:
                self.disconnect(connection_id, user_id)


manager = ConnectionManager()


@websocket_router.websocket("/query/{connection_id}")
async def websocket_query_endpoint(
    websocket: WebSocket, connection_id: str, token: Optional[str] = Query(None)
):
    # Authenticate user
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    try:
        security_manager = SecurityManager()
        payload = security_manager.verify_token(token)
        user_id = payload.get("user_id")

        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return

    except Exception as e:
        await websocket.close(code=4001, reason=f"Authentication failed: {str(e)}")
        return

    # Connect user
    await manager.connect(websocket, connection_id, user_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await manager.send_personal_message(
                    {"type": "error", "message": "Invalid JSON format"}, connection_id
                )
                continue

            message_type = message.get("type")

            if message_type == "query":
                await handle_query_message(message, connection_id, user_id)
            elif message_type == "ping":
                await manager.send_personal_message(
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                    connection_id,
                )
            else:
                await manager.send_personal_message(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {message_type}",
                    },
                    connection_id,
                )

    except WebSocketDisconnect:
        manager.disconnect(connection_id, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
        manager.disconnect(connection_id, user_id)


async def handle_query_message(message: dict, connection_id: str, user_id: int):
    """Handle query execution via WebSocket"""
    query = message.get("query", "").strip()

    if not query:
        await manager.send_personal_message(
            {"type": "error", "message": "Empty query"}, connection_id
        )
        return

    # Send processing status
    await manager.send_personal_message(
        {
            "type": "status",
            "message": "Processing your query...",
            "timestamp": datetime.utcnow().isoformat(),
        },
        connection_id,
    )

    try:
        # Simulate query processing (will be replaced with actual NL2SQL in Phase 2)
        await asyncio.sleep(1)  # Simulate processing time

        # Mock SQL and results for Phase 1
        mock_sql = "SELECT COUNT(*) as total_patients FROM patients;"
        results = await db_manager.execute_query(mock_sql)
        results_list = [dict(record) for record in results]

        # Send results
        await manager.send_personal_message(
            {
                "type": "result",
                "query": query,
                "sql": mock_sql,
                "results": results_list,
                "row_count": len(results_list),
                "timestamp": datetime.utcnow().isoformat(),
            },
            connection_id,
        )

    except Exception as e:
        await manager.send_personal_message(
            {
                "type": "error",
                "message": f"Query execution failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
            },
            connection_id,
        )
