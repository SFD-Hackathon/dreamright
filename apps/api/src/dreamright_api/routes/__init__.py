"""API routes."""

from .projects import router as projects_router
from .story import router as story_router
from .characters import router as characters_router
from .locations import router as locations_router
from .chapters import router as chapters_router
from .panels import router as panels_router
from .jobs import router as jobs_router
from .assets import router as assets_router

__all__ = [
    "projects_router",
    "story_router",
    "characters_router",
    "locations_router",
    "chapters_router",
    "panels_router",
    "jobs_router",
    "assets_router",
]
