import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from backend.core.security import decode_access_token
from backend.api.websocket_manager import ws_manager

router = APIRouter()
logger = structlog.get_logger("aboutcloud.ws")


@router.websocket("/live")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    tenant_id = _extract_tenant(token)
    if not tenant_id:
        await websocket.close(code=4001, reason="Invalid or missing token")
        return

    await ws_manager.connect(websocket, tenant_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, tenant_id)
    except Exception as exc:
        logger.warning("ws_error", error=str(exc))
        ws_manager.disconnect(websocket, tenant_id)


def _extract_tenant(token: str) -> str | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        return payload.get("sub")
    except (ValueError, Exception):
        return None
