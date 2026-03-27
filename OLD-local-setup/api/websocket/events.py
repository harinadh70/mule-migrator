"""
Event publisher — convenience functions for pushing events to Redis pub/sub.

These functions are imported by Celery tasks (and optionally by API route
handlers) to notify WebSocket clients about pipeline progress, build output,
and other real-time events.

All events follow a uniform schema::

    {
        "type": "<event_type>",
        "agent": "<agent_name>",       # optional
        "status": "<status_string>",    # optional
        "data": { ... },
        "timestamp": 1711036800.123,
        "correlation_id": "<migration_or_build_id>"
    }
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import redis.asyncio as aioredis
import structlog

from api.config import get_settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
#  Redis connection (lazy singleton for the async context)
# ---------------------------------------------------------------------------

_publisher_redis: Optional[aioredis.Redis] = None


async def _get_publisher_redis() -> aioredis.Redis:
    """Return (or create) a long-lived Redis connection for publishing."""
    global _publisher_redis
    if _publisher_redis is None:
        settings = get_settings()
        _publisher_redis = aioredis.from_url(
            settings.redis.url,
            decode_responses=True,
        )
    return _publisher_redis


async def close_publisher_redis() -> None:
    """Tear down the publisher Redis connection (call at app shutdown)."""
    global _publisher_redis
    if _publisher_redis is not None:
        await _publisher_redis.close()
        _publisher_redis = None


# ---------------------------------------------------------------------------
#  Low-level publish
# ---------------------------------------------------------------------------


async def _publish_to_channel(
    channel: str,
    event: Dict[str, Any],
    *,
    store_for_replay: bool = True,
    max_replay_events: int = 500,
    replay_ttl_seconds: int = 86400,
) -> None:
    """
    Publish a JSON-serialized event to a Redis pub/sub channel.

    Optionally stores the event in a sorted set (keyed by timestamp) so
    that reconnecting WebSocket clients can replay missed events.

    Args:
        channel: Redis pub/sub channel name.
        event: The event payload dict (must be JSON-serializable).
        store_for_replay: Whether to persist in the replay sorted set.
        max_replay_events: Maximum number of events retained for replay.
        replay_ttl_seconds: TTL on the replay sorted set key.
    """
    redis = await _get_publisher_redis()
    payload = json.dumps(event, default=str)

    await redis.publish(channel, payload)

    if store_for_replay:
        replay_key = f"{channel}:log"
        score = event.get("timestamp", time.time())
        await redis.zadd(replay_key, {payload: score})
        # Trim to keep only the most recent events
        await redis.zremrangebyrank(replay_key, 0, -(max_replay_events + 1))
        await redis.expire(replay_key, replay_ttl_seconds)

    logger.debug(
        "event.published",
        channel=channel,
        event_type=event.get("type"),
    )


# ---------------------------------------------------------------------------
#  Migration events
# ---------------------------------------------------------------------------


async def publish_migration_event(
    migration_id: str,
    event: Dict[str, Any],
) -> None:
    """
    Publish an event to the migration's Redis channel.

    Args:
        migration_id: UUID of the migration.
        event: Event dict (must include ``type``).
    """
    event.setdefault("timestamp", time.time())
    event.setdefault("correlation_id", migration_id)
    channel = f"migration:{migration_id}:events"
    await _publish_to_channel(channel, event)


async def publish_agent_progress(
    migration_id: str,
    agent_name: str,
    status: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Convenience wrapper: publish an agent progress event.

    Args:
        migration_id: UUID of the migration.
        agent_name: Name of the agent (e.g. ``"planner"``, ``"coder"``).
        status: Agent status string (``"started"``, ``"completed"``, ``"failed"``).
        data: Optional extra data (duration, tokens, findings, score, etc.).
    """
    event = {
        "type": f"agent_{status}",
        "agent": agent_name,
        "status": status,
        "data": data or {},
        "timestamp": time.time(),
        "correlation_id": migration_id,
    }
    await publish_migration_event(migration_id, event)


# ---------------------------------------------------------------------------
#  Build events
# ---------------------------------------------------------------------------


async def publish_build_event(
    build_id: str,
    event: Dict[str, Any],
) -> None:
    """
    Publish an event to the build's Redis channel.

    Args:
        build_id: UUID of the build job.
        event: Event dict (must include ``type``).
    """
    event.setdefault("timestamp", time.time())
    event.setdefault("correlation_id", build_id)
    channel = f"build:{build_id}:output"
    await _publish_to_channel(channel, event)


# ---------------------------------------------------------------------------
#  Replay helper (used by WebSocket handlers on reconnection)
# ---------------------------------------------------------------------------


async def get_replay_events(
    channel: str,
    after_timestamp: float = 0.0,
    limit: int = 200,
) -> list[Dict[str, Any]]:
    """
    Retrieve stored events from the replay sorted set, optionally
    filtering to events newer than *after_timestamp*.

    Args:
        channel: The Redis channel name (e.g. ``migration:<id>:events``).
        after_timestamp: Only return events with timestamp > this value.
        limit: Maximum number of events to return.

    Returns:
        A list of event dicts ordered by timestamp ascending.
    """
    redis = await _get_publisher_redis()
    replay_key = f"{channel}:log"

    # Use ZRANGEBYSCORE to get events after the given timestamp
    raw_events = await redis.zrangebyscore(
        replay_key,
        min=f"({after_timestamp}" if after_timestamp > 0 else "-inf",
        max="+inf",
        start=0,
        num=limit,
    )

    events = []
    for raw in raw_events:
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError:
            continue

    return events
