"""
Plugin System для расширяемой архитектуры
"""
from .plugin_manager import PluginManager, Plugin, PluginMetadata
from .base_plugins import MessagePlugin, CallbackPlugin, AIPlugin

__all__ = [
    'PluginManager',
    'Plugin',
    'PluginMetadata',
    'MessagePlugin',
    'CallbackPlugin',
    'AIPlugin'
]
