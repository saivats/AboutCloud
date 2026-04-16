import json
import asyncio
from typing import Dict, Set
from datetime import datetime

from fastapi import WebSocket
import structlog

logger = structlog.get_logger("aboutcloud.websocket")


class ConnectionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connections: Dict[str, Set[WebSocket]] = {}
            cls._instance._broadcast_connections: Set[WebSocket] = set()
        return cls._instance

    async def connect(self, websocket: WebSocket, tenant_id: str):
        await websocket.accept()
        if tenant_id not in self._connections:
            self._connections[tenant_id] = set()
        self._connections[tenant_id].add(websocket)
        self._broadcast_connections.add(websocket)
        logger.info("ws_connected", tenant_id=tenant_id)

    def disconnect(self, websocket: WebSocket, tenant_id: str):
        if tenant_id in self._connections:
            self._connections[tenant_id].discard(websocket)
            if not self._connections[tenant_id]:
                del self._connections[tenant_id]
        self._broadcast_connections.discard(websocket)
        logger.info("ws_disconnected", tenant_id=tenant_id)

    async def send_to_tenant(self, tenant_id: str, data: dict):
        if tenant_id not in self._connections:
            return

        stale = set()
        for ws in self._connections[tenant_id]:
            try:
                await ws.send_json(data)
            except Exception:
                stale.add(ws)

        for ws in stale:
            self._connections[tenant_id].discard(ws)
            self._broadcast_connections.discard(ws)

    async def broadcast_anomaly(self, anomaly_data: dict):
        tenant_id = anomaly_data.get("tenant_id")
        if tenant_id:
            await self.send_to_tenant(tenant_id, {
                "type": "anomaly_detected",
                "timestamp": datetime.utcnow().isoformat(),
                "payload": anomaly_data,
            })

    async def broadcast_health_update(self, tenant_id: str, health_data: dict):
        await self.send_to_tenant(tenant_id, {
            "type": "health_update",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": health_data,
        })

    @property
    def active_connections_count(self) -> int:
        return len(self._broadcast_connections)

    @property
    def active_tenants(self) -> list:
        return list(self._connections.keys())


ws_manager = ConnectionManager()
