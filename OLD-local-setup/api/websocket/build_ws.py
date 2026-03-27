"""
Build WebSocket endpoint — /ws/build/{build_id}

Subscribes to the Redis channel ``build:<id>:output`` and streams
Maven build log lines to connected clients in real time.

Events include:
  - build_started — build process has begun
  - build_output  — a single line of build console output
  - build_complete — build finished successfully (exit code 0)
  - build_failed  — build finished with errors (exit code != 0)
  - heartbeat     — keep-alive ping (every 30 s)
"""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from api.websocket.events import get_replay_events
from api.websocket.manager import connection_manager

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/build/{build_id}")
async def build_websocket(
    websocket: WebSocket,
    build_id: str,
    last_event_id: Optional[float] = Query(
        default=None,
        description=(
            "Unix timestamp of the last event the client received. "
            "Events after this timestamp will be replayed."
        ),
    ),
    user_id: Optional[str] = Query(
        default=None,
        description="Optional user ID for connection-limit enforcement.",
    ),
) -> None:
    """
    WebSocket endpoint for streaming build output in real time.

    Connect to ``/ws/build/<uuid>`` to watch Maven build output line
    by line as the build executes on the Celery worker.

    **Reconnection support**: Pass ``?last_event_id=<timestamp>`` to
    replay build output that occurred after the given timestamp.

    **Message schema** (JSON)::

        {
            "type": "build_output",
            "data": {
                "line": "[INFO] Compiling 42 source files...",
                "line_number": 17
            },
            "timestamp": 1711036800.456,
            "correlation_id": "<build_id>"
        }

    **Event types**:
      - ``connected`` — sent immediately after the WS handshake
      - ``build_started`` — the build process has been launched
      - ``build_output`` — one line of Maven stdout/stderr
      - ``build_complete`` — build succeeded (exit code 0)
      - ``build_failed`` — build failed (exit code != 0)
      - ``heartbeat`` — keep-alive ping (every 30 s)
    """
    accepted = await connection_manager.connect(
        websocket,
        resource_id=build_id,
        resource_type="build",
        user_id=user_id,
    )
    if not accepted:
        return

    try:
        # Replay missed events if reconnecting
        if last_event_id is not None:
            channel = f"build:{build_id}:output"
            missed_events = await get_replay_events(
                channel,
                after_timestamp=last_event_id,
                limit=500,
            )

            logger.info(
                "ws.build.replaying",
                build_id=build_id,
                missed_count=len(missed_events),
                after=last_event_id,
            )

            for event in missed_events:
                try:
                    await websocket.send_json(event)
                except Exception:
                    break

        # Subscribe to the Redis channel and forward live events
        channel = f"build:{build_id}:output"
        await connection_manager.subscribe_and_forward(
            websocket,
            channel,
            resource_id=build_id,
        )

    except WebSocketDisconnect:
        logger.info(
            "ws.build.client_disconnected",
            build_id=build_id,
        )
    except Exception as exc:
        logger.error(
            "ws.build.error",
            build_id=build_id,
            error=str(exc),
            exc_info=True,
        )
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "Internal server error"},
                "correlation_id": build_id,
            })
        except Exception:
            pass
    finally:
        connection_manager.disconnect(websocket)
