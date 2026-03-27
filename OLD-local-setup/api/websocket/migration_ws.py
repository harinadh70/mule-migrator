"""
Migration WebSocket endpoint — /ws/migration/{migration_id}

Subscribes to the Redis channel ``migration:<id>:events`` and forwards
all pipeline events to connected browser clients in real time.

Events include:
  - agent_started, agent_completed, agent_failed, agent_bypassed
  - pipeline_started, pipeline_complete, pipeline_failed
  - progress_update
  - error, heartbeat

Supports ``last_event_id`` query parameter for replaying missed events
after a reconnection.
"""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from api.websocket.events import get_replay_events
from api.websocket.manager import connection_manager

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/migration/{migration_id}")
async def migration_websocket(
    websocket: WebSocket,
    migration_id: str,
    last_event_id: Optional[float] = Query(
        default=None,
        description=(
            "Unix timestamp of the last event the client received. "
            "Events after this timestamp will be replayed before "
            "switching to live streaming."
        ),
    ),
    user_id: Optional[str] = Query(
        default=None,
        description="Optional user ID for connection-limit enforcement.",
    ),
) -> None:
    """
    WebSocket endpoint for streaming migration pipeline events.

    Connect to ``/ws/migration/<uuid>`` to receive real-time updates
    as each agent in the migration pipeline starts, completes, or fails.

    **Reconnection support**: Pass ``?last_event_id=<timestamp>`` to
    replay any events that occurred between the last received event and
    now, then seamlessly switch to live streaming.

    **Message schema** (JSON)::

        {
            "type": "agent_completed",
            "agent": "coder",
            "status": "completed",
            "data": {
                "duration_ms": 12345,
                "tokens": 4096,
                "findings": [...],
                "score": 0.92
            },
            "timestamp": 1711036800.123,
            "correlation_id": "<migration_id>"
        }

    **Event types**:
      - ``connected`` — sent immediately after the WS handshake
      - ``agent_started`` — an agent has begun processing
      - ``agent_completed`` — an agent finished successfully
      - ``agent_failed`` — an agent encountered an error
      - ``agent_bypassed`` — an agent was skipped (circuit breaker)
      - ``pipeline_started`` — the pipeline has begun execution
      - ``pipeline_complete`` — migration finished (check ``status``)
      - ``migration_complete`` — alias for pipeline_complete
      - ``progress_update`` — intermediate progress percentage
      - ``error`` — an error event
      - ``heartbeat`` — keep-alive ping (every 30 s)
    """
    # Register connection
    accepted = await connection_manager.connect(
        websocket,
        resource_id=migration_id,
        resource_type="migration",
        user_id=user_id,
    )
    if not accepted:
        return  # connection was rejected (limit exceeded)

    try:
        # Replay missed events if reconnecting
        if last_event_id is not None:
            channel = f"migration:{migration_id}:events"
            missed_events = await get_replay_events(
                channel,
                after_timestamp=last_event_id,
                limit=200,
            )

            logger.info(
                "ws.migration.replaying",
                migration_id=migration_id,
                missed_count=len(missed_events),
                after=last_event_id,
            )

            for event in missed_events:
                try:
                    await websocket.send_json(event)
                except Exception:
                    break

        # Subscribe to the Redis channel and forward live events
        channel = f"migration:{migration_id}:events"
        await connection_manager.subscribe_and_forward(
            websocket,
            channel,
            resource_id=migration_id,
        )

    except WebSocketDisconnect:
        logger.info(
            "ws.migration.client_disconnected",
            migration_id=migration_id,
        )
    except Exception as exc:
        logger.error(
            "ws.migration.error",
            migration_id=migration_id,
            error=str(exc),
            exc_info=True,
        )
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "Internal server error"},
                "correlation_id": migration_id,
            })
        except Exception:
            pass
    finally:
        connection_manager.disconnect(websocket)
