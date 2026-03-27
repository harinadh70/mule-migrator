"""
ConnectionManager — central registry for active WebSocket connections.

Handles:
  - Per-resource (migration/build) connection tracking
  - Heartbeat pings every 30 seconds to detect dead connections
  - Per-user connection limits (max 5 simultaneous)
  - Redis pub/sub subscription for cross-process event delivery
  - Graceful disconnect and cleanup
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from typing import Any, Callable, Dict, Optional, Set

import redis.asyncio as aioredis
import structlog
from fastapi import WebSocket, WebSocketDisconnect

from api.config import get_settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
#  Message schema helper
# ---------------------------------------------------------------------------


def _build_message(
    msg_type: str,
    *,
    agent: Optional[str] = None,
    status: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a uniform WebSocket message following the project schema.

    Schema::

        {
            "type": "<msg_type>",
            "agent": "<agent_name>",        # optional
            "status": "<status>",            # optional
            "data": { ... },
            "timestamp": 1711036800.123,
            "correlation_id": "<id>"
        }
    """
    return {
        "type": msg_type,
        "agent": agent,
        "status": status,
        "data": data or {},
        "timestamp": time.time(),
        "correlation_id": correlation_id,
    }


# ---------------------------------------------------------------------------
#  Connection wrapper
# ---------------------------------------------------------------------------


class _TrackedConnection:
    """Internal bookkeeping for a single WebSocket connection."""

    __slots__ = (
        "websocket",
        "resource_id",
        "resource_type",
        "user_id",
        "connected_at",
        "last_pong",
    )

    def __init__(
        self,
        websocket: WebSocket,
        resource_id: str,
        resource_type: str,
        user_id: Optional[str] = None,
    ) -> None:
        self.websocket = websocket
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.user_id = user_id
        self.connected_at = time.time()
        self.last_pong = time.time()


# ---------------------------------------------------------------------------
#  ConnectionManager
# ---------------------------------------------------------------------------


class ConnectionManager:
    """
    Singleton manager for all active WebSocket connections.

    Usage::

        manager = ConnectionManager()

        # In a WS endpoint:
        await manager.connect(ws, resource_id="abc", resource_type="migration")
        try:
            await manager.subscribe_and_forward(ws, "migration:abc:events")
        finally:
            manager.disconnect(ws)

    The manager runs a background heartbeat loop that pings every 30 s
    and disconnects clients that fail to pong within 60 s.
    """

    MAX_CONNECTIONS_PER_USER = 5
    HEARTBEAT_INTERVAL_S = 30
    DEAD_CONNECTION_TIMEOUT_S = 60

    def __init__(self) -> None:
        # resource_id -> set of tracked connections
        self._connections: Dict[str, Set[_TrackedConnection]] = defaultdict(set)
        # user_id -> count of active connections
        self._user_connection_count: Dict[str, int] = defaultdict(int)
        # ws -> tracked connection (reverse lookup)
        self._ws_map: Dict[WebSocket, _TrackedConnection] = {}
        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._subscriber_tasks: Dict[str, asyncio.Task] = {}
        # Redis pub/sub connections (one per subscription channel)
        self._pubsubs: Dict[str, aioredis.client.PubSub] = {}

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    def start_heartbeat(self) -> None:
        """Launch the background heartbeat loop (call once at app startup)."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(),
                name="ws-heartbeat",
            )
            logger.info("ws.heartbeat_started")

    async def shutdown(self) -> None:
        """Gracefully tear down all connections and background tasks."""
        # Cancel heartbeat
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Cancel all subscriber tasks
        for task in self._subscriber_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._subscriber_tasks.clear()

        # Close all pub/sub connections
        for ps in self._pubsubs.values():
            try:
                await ps.unsubscribe()
                await ps.close()
            except Exception:
                pass
        self._pubsubs.clear()

        # Disconnect all websockets
        all_conns = list(self._ws_map.values())
        for conn in all_conns:
            try:
                await conn.websocket.close(code=1001, reason="Server shutting down")
            except Exception:
                pass
        self._connections.clear()
        self._ws_map.clear()
        self._user_connection_count.clear()

        logger.info("ws.manager_shutdown_complete")

    # ------------------------------------------------------------------
    #  Connect / Disconnect
    # ------------------------------------------------------------------

    async def connect(
        self,
        websocket: WebSocket,
        resource_id: str,
        resource_type: str = "migration",
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Accept and register a WebSocket connection.

        Returns False (and closes the WS) if the per-user limit is exceeded.
        """
        # Enforce per-user limit
        if user_id and self._user_connection_count[user_id] >= self.MAX_CONNECTIONS_PER_USER:
            logger.warning(
                "ws.connection_limit_exceeded",
                user_id=user_id,
                limit=self.MAX_CONNECTIONS_PER_USER,
            )
            await websocket.close(
                code=4029,
                reason=f"Connection limit ({self.MAX_CONNECTIONS_PER_USER}) exceeded",
            )
            return False

        await websocket.accept()

        tracked = _TrackedConnection(
            websocket=websocket,
            resource_id=resource_id,
            resource_type=resource_type,
            user_id=user_id,
        )
        self._connections[resource_id].add(tracked)
        self._ws_map[websocket] = tracked
        if user_id:
            self._user_connection_count[user_id] += 1

        logger.info(
            "ws.connected",
            resource_id=resource_id,
            resource_type=resource_type,
            user_id=user_id,
            total_for_resource=len(self._connections[resource_id]),
        )

        # Send welcome message
        await self.send_personal(websocket, _build_message(
            "connected",
            data={"resource_id": resource_id, "resource_type": resource_type},
            correlation_id=resource_id,
        ))

        return True

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection from tracking.

        Safe to call multiple times — idempotent.
        """
        tracked = self._ws_map.pop(websocket, None)
        if tracked is None:
            return

        self._connections[tracked.resource_id].discard(tracked)
        if not self._connections[tracked.resource_id]:
            del self._connections[tracked.resource_id]

        if tracked.user_id:
            self._user_connection_count[tracked.user_id] = max(
                0, self._user_connection_count[tracked.user_id] - 1
            )

        logger.info(
            "ws.disconnected",
            resource_id=tracked.resource_id,
            resource_type=tracked.resource_type,
            user_id=tracked.user_id,
        )

    # ------------------------------------------------------------------
    #  Sending
    # ------------------------------------------------------------------

    async def send_personal(
        self,
        websocket: WebSocket,
        message: Dict[str, Any],
    ) -> None:
        """Send a JSON message to a single WebSocket."""
        try:
            await websocket.send_json(message)
        except Exception as exc:
            logger.debug("ws.send_failed", error=str(exc))
            self.disconnect(websocket)

    async def broadcast_to_resource(
        self,
        resource_id: str,
        message: Dict[str, Any],
    ) -> None:
        """Send a JSON message to all connections watching a given resource."""
        connections = list(self._connections.get(resource_id, set()))
        dead: list[_TrackedConnection] = []

        for conn in connections:
            try:
                await conn.websocket.send_json(message)
            except Exception:
                dead.append(conn)

        # Clean up dead connections
        for conn in dead:
            self.disconnect(conn.websocket)

    # ------------------------------------------------------------------
    #  Redis pub/sub subscription
    # ------------------------------------------------------------------

    async def subscribe_and_forward(
        self,
        websocket: WebSocket,
        channel: str,
        *,
        resource_id: Optional[str] = None,
    ) -> None:
        """
        Subscribe to a Redis pub/sub channel and forward messages to the
        WebSocket until the client disconnects.

        This is a blocking call — it runs in the WS handler's task and
        only returns when the client disconnects or an error occurs.

        Args:
            websocket: The WebSocket to forward messages to.
            channel: Redis pub/sub channel to subscribe to.
            resource_id: Optional correlation ID for log context.
        """
        settings = get_settings()
        redis = aioredis.from_url(settings.redis.url, decode_responses=True)
        pubsub = redis.pubsub()

        try:
            await pubsub.subscribe(channel)
            logger.info("ws.subscribed", channel=channel, resource_id=resource_id)

            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=self.HEARTBEAT_INTERVAL_S,
                        ),
                        timeout=self.HEARTBEAT_INTERVAL_S + 5,
                    )
                except asyncio.TimeoutError:
                    # No message — send heartbeat
                    try:
                        await websocket.send_json(_build_message(
                            "heartbeat",
                            correlation_id=resource_id,
                        ))
                        # Update last pong
                        tracked = self._ws_map.get(websocket)
                        if tracked:
                            tracked.last_pong = time.time()
                    except Exception:
                        break
                    continue

                if message is None:
                    # No message yet, send heartbeat
                    try:
                        await websocket.send_json(_build_message(
                            "heartbeat",
                            correlation_id=resource_id,
                        ))
                    except Exception:
                        break
                    continue

                if message["type"] == "message":
                    try:
                        event_data = json.loads(message["data"])
                    except (json.JSONDecodeError, TypeError):
                        event_data = {"type": "raw", "data": str(message["data"])}

                    try:
                        await websocket.send_json(event_data)
                    except Exception:
                        break

                # Also listen for incoming client messages (e.g. pong, cancel)
                try:
                    client_msg = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=0.01,
                    )
                    await self._handle_client_message(websocket, client_msg)
                except asyncio.TimeoutError:
                    pass
                except WebSocketDisconnect:
                    break
                except Exception:
                    pass

        except WebSocketDisconnect:
            logger.info("ws.client_disconnected", channel=channel)
        except asyncio.CancelledError:
            logger.info("ws.subscription_cancelled", channel=channel)
        except Exception as exc:
            logger.error(
                "ws.subscription_error",
                channel=channel,
                error=str(exc),
                exc_info=True,
            )
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
                await redis.close()
            except Exception:
                pass

    async def _handle_client_message(
        self,
        websocket: WebSocket,
        raw_message: str,
    ) -> None:
        """Process a message received from the WebSocket client."""
        try:
            msg = json.loads(raw_message)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type", "")
        tracked = self._ws_map.get(websocket)

        if msg_type == "pong":
            if tracked:
                tracked.last_pong = time.time()
        elif msg_type == "ping":
            await self.send_personal(websocket, _build_message(
                "pong",
                correlation_id=tracked.resource_id if tracked else None,
            ))

    # ------------------------------------------------------------------
    #  Heartbeat loop
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """
        Periodically ping all connected clients and disconnect dead ones.

        Runs forever until cancelled.
        """
        while True:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL_S)

                now = time.time()
                dead: list[WebSocket] = []

                for ws, tracked in list(self._ws_map.items()):
                    # Check for dead connections
                    if now - tracked.last_pong > self.DEAD_CONNECTION_TIMEOUT_S:
                        dead.append(ws)
                        continue

                    # Send ping
                    try:
                        await ws.send_json(_build_message(
                            "heartbeat",
                            correlation_id=tracked.resource_id,
                        ))
                    except Exception:
                        dead.append(ws)

                for ws in dead:
                    logger.info("ws.dead_connection_removed")
                    try:
                        await ws.close(code=1001, reason="Connection timed out")
                    except Exception:
                        pass
                    self.disconnect(ws)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("ws.heartbeat_error", error=str(exc))

    # ------------------------------------------------------------------
    #  Introspection
    # ------------------------------------------------------------------

    def get_connection_count(self, resource_id: Optional[str] = None) -> int:
        """Return the number of active connections, optionally for a resource."""
        if resource_id:
            return len(self._connections.get(resource_id, set()))
        return len(self._ws_map)

    def get_connected_resources(self) -> list[str]:
        """Return list of resource IDs with at least one active connection."""
        return [rid for rid, conns in self._connections.items() if conns]


# ---------------------------------------------------------------------------
#  Module-level singleton
# ---------------------------------------------------------------------------

connection_manager = ConnectionManager()
