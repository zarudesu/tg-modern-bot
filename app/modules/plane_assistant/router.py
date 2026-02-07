"""Router for /plane AI assistant module."""

from aiogram import Router

from .handlers import router as handlers_router

router = Router(name="plane_assistant_module")
router.include_router(handlers_router)
