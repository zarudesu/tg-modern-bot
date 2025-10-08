"""Task Reports metadata handlers package."""

from .duration import router as duration_router
from .travel import router as travel_router
from .company import router as company_router
from .workers import router as workers_router
from .navigation import router as navigation_router

__all__ = [
    "duration_router",
    "travel_router",
    "company_router",
    "workers_router",
    "navigation_router",
]
