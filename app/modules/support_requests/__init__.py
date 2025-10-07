"""
Support Requests Module

Позволяет пользователям создавать заявки в Plane из групповых чатов.
Автоматически определяет проект по чату и уведомляет админов.
"""

from .router import router

__all__ = ['router']
