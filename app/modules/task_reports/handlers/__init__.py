"""
Task Reports handlers package

Exports all handler routers for task reports module
"""

from .creation import router as creation_router
from .preview import router as preview_router
from .edit import router as edit_router
from .approval import router as approval_router
from .ai_generation import router as ai_generation_router
from .voice_fill import router as voice_fill_router

__all__ = [
    "creation_router",
    "preview_router",
    "edit_router",
    "approval_router",
    "ai_generation_router",
    "voice_fill_router",
]
