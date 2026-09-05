import asyncio
import json
import logging
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis
from backend.app.core.config import settings

logger = logging.getLogger("sentinel.websockets")
router = APIRouter(tags=["Real-Time WebSockets"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        for dead in dead_connections:
            self.active_connections.discard(dead)

manager = ConnectionManager()

@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep-alive heartbeat from client
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def redis_alert_listener():
    """Background task listening for Redis PubSub alerts and broadcasting to WebSockets."""
    if settings.REDIS_URL:
        r = aioredis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    else:
        r = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
    pubsub = r.pubsub()
    await pubsub.subscribe("sentinel:alerts:live")
    logger.info("Subscribed to Redis sentinel:alerts:live channel for real-time WebSocket dispatch.")

    try:
        async for msg in pubsub.listen():
            if msg and msg["type"] == "message":
                payload = json.loads(msg["data"])
                await manager.broadcast(payload)
    except asyncio.CancelledError:
        await pubsub.unsubscribe("sentinel:alerts:live")
        await r.close()
    except Exception as e:
        logger.error(f"Redis listener error: {e}")
