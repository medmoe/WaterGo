import uuid

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jwt.exceptions import InvalidTokenError

from app.api.deps import SessionDep
from app.core import security
from app.core.config import settings
from app.models import User, UserRole
from app.services.ws import manager

router = APIRouter(prefix="/ws", tags=["realtime"])


def _user_from_token(session: SessionDep, token: str | None) -> User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
    except InvalidTokenError:
        return None
    user = session.get(User, payload.get("sub"))
    if not user or not user.is_active:
        return None
    return user


@router.websocket("/dispatch")
async def dispatch_channel(
    websocket: WebSocket, session: SessionDep, token: str | None = None
) -> None:
    """Pushes new confirmed orders and route status changes to the board."""
    user = _user_from_token(session, token)
    if not user or user.role not in (UserRole.dispatcher, UserRole.admin):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await manager.connect_dispatch(websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive / ignore client messages
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_dispatch(websocket)


@router.websocket("/driver/{driver_id}")
async def driver_channel(
    websocket: WebSocket,
    session: SessionDep,
    driver_id: uuid.UUID,
    token: str | None = None,
) -> None:
    """Pushes new route assignments to one driver."""
    user = _user_from_token(session, token)
    if not user or (user.id != driver_id and user.role != UserRole.admin):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await manager.connect_driver(driver_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_driver(driver_id, websocket)
