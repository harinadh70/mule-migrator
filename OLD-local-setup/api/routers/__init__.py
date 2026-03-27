"""
API routers package.

Versioned sub-packages (v1, v2) contain the actual route definitions.
Each module exposes a ``router`` attribute (an ``APIRouter`` instance)
that is dynamically imported and mounted in ``api.main``.
"""
