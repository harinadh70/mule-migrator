"""
WebSocket real-time communication layer.

Provides live progress streaming for migrations and builds via
Redis pub/sub backed WebSocket connections.

Mount the routers in your FastAPI app::

    from api.websocket.migration_ws import router as migration_ws_router
    from api.websocket.build_ws import router as build_ws_router

    app.include_router(migration_ws_router)
    app.include_router(build_ws_router)
"""

from api.websocket.manager import ConnectionManager

__all__ = ["ConnectionManager"]
