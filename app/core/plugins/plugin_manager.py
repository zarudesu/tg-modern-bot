"""
Plugin Manager - управление плагинами

Позволяет динамически загружать/выгружать функциональность
"""
import importlib
import inspect
from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
from pathlib import Path

from ...utils.logger import bot_logger
from ..events.event_bus import EventHandler, event_bus


@dataclass
class PluginMetadata:
    """Метаданные плагина"""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str] = None
    enabled: bool = True

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class Plugin(ABC):
    """
    Базовый класс для всех плагинов

    Плагин может:
    - Регистрировать обработчики событий
    - Добавлять команды бота
    - Предоставлять API для других плагинов
    """

    def __init__(self):
        self._event_handlers: List[EventHandler] = []
        self._initialized = False

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Метаданные плагина"""
        pass

    async def on_load(self):
        """
        Вызывается при загрузке плагина
        Здесь можно инициализировать ресурсы, регистрировать обработчики и т.д.
        """
        pass

    async def on_unload(self):
        """
        Вызывается при выгрузке плагина
        Здесь нужно освободить ресурсы
        """
        # Автоматически отменяем регистрацию всех обработчиков событий
        for handler in self._event_handlers:
            event_bus.unregister_handler(handler)

    def register_event_handler(self, handler: EventHandler):
        """Регистрация обработчика событий"""
        self._event_handlers.append(handler)
        event_bus.register_handler(handler)

    async def on_error(self, error: Exception):
        """Обработка ошибок плагина"""
        bot_logger.error(
            f"Plugin error: {self.metadata.name}",
            extra={"error": str(error)}
        )

    @property
    def is_initialized(self) -> bool:
        """Проверка инициализации плагина"""
        return self._initialized


class PluginManager:
    """
    Plugin Manager - управление всеми плагинами

    Singleton для централизованного управления плагинами
    """
    _instance = None
    _plugins: Dict[str, Plugin] = {}
    _plugin_dependencies: Dict[str, List[str]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def load_plugin(self, plugin: Plugin) -> bool:
        """
        Загрузка плагина

        Args:
            plugin: Экземпляр плагина для загрузки

        Returns:
            True если плагин загружен успешно
        """
        plugin_name = plugin.metadata.name

        # Проверяем зависимости
        if not await self._check_dependencies(plugin):
            bot_logger.error(
                f"Plugin {plugin_name} dependencies not met",
                extra={"dependencies": plugin.metadata.dependencies}
            )
            return False

        try:
            # Загружаем плагин
            await plugin.on_load()
            plugin._initialized = True

            # Сохраняем плагин
            self._plugins[plugin_name] = plugin
            self._plugin_dependencies[plugin_name] = plugin.metadata.dependencies

            bot_logger.info(
                f"Plugin loaded: {plugin_name} v{plugin.metadata.version}",
                extra={"author": plugin.metadata.author}
            )
            return True

        except Exception as e:
            bot_logger.error(
                f"Failed to load plugin: {plugin_name}",
                extra={"error": str(e)}
            )
            await plugin.on_error(e)
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        Выгрузка плагина

        Args:
            plugin_name: Имя плагина для выгрузки

        Returns:
            True если плагин выгружен успешно
        """
        if plugin_name not in self._plugins:
            bot_logger.warning(f"Plugin not found: {plugin_name}")
            return False

        # Проверяем, что другие плагины не зависят от этого
        dependent_plugins = self._get_dependent_plugins(plugin_name)
        if dependent_plugins:
            bot_logger.error(
                f"Cannot unload plugin {plugin_name}: other plugins depend on it",
                extra={"dependent_plugins": dependent_plugins}
            )
            return False

        try:
            plugin = self._plugins[plugin_name]
            await plugin.on_unload()

            del self._plugins[plugin_name]
            del self._plugin_dependencies[plugin_name]

            bot_logger.info(f"Plugin unloaded: {plugin_name}")
            return True

        except Exception as e:
            bot_logger.error(
                f"Failed to unload plugin: {plugin_name}",
                extra={"error": str(e)}
            )
            return False

    async def reload_plugin(self, plugin_name: str) -> bool:
        """Перезагрузка плагина"""
        if plugin_name not in self._plugins:
            return False

        plugin = self._plugins[plugin_name]

        # Выгружаем
        if not await self.unload_plugin(plugin_name):
            return False

        # Загружаем заново
        return await self.load_plugin(plugin)

    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """Получить плагин по имени"""
        return self._plugins.get(plugin_name)

    def get_all_plugins(self) -> List[Plugin]:
        """Получить все загруженные плагины"""
        return list(self._plugins.values())

    def get_plugin_info(self, plugin_name: str) -> Optional[PluginMetadata]:
        """Получить информацию о плагине"""
        plugin = self.get_plugin(plugin_name)
        return plugin.metadata if plugin else None

    async def _check_dependencies(self, plugin: Plugin) -> bool:
        """Проверка зависимостей плагина"""
        for dep in plugin.metadata.dependencies:
            if dep not in self._plugins:
                return False
            if not self._plugins[dep].is_initialized:
                return False
        return True

    def _get_dependent_plugins(self, plugin_name: str) -> List[str]:
        """Получить список плагинов которые зависят от данного"""
        dependent = []
        for name, deps in self._plugin_dependencies.items():
            if plugin_name in deps:
                dependent.append(name)
        return dependent

    async def load_plugins_from_directory(self, directory: str):
        """
        Автоматическая загрузка всех плагинов из директории

        Args:
            directory: Путь к директории с плагинами
        """
        plugin_dir = Path(directory)

        if not plugin_dir.exists():
            bot_logger.warning(f"Plugin directory not found: {directory}")
            return

        # Импортируем все Python модули из директории
        for plugin_file in plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue

            try:
                module_name = f"app.plugins.{plugin_file.stem}"
                module = importlib.import_module(module_name)

                # Находим классы плагинов в модуле
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                        issubclass(obj, Plugin) and
                        obj != Plugin):

                        # Создаём экземпляр и загружаем
                        plugin_instance = obj()
                        await self.load_plugin(plugin_instance)

            except Exception as e:
                bot_logger.error(
                    f"Failed to import plugin from {plugin_file}",
                    extra={"error": str(e)}
                )

    @property
    def loaded_plugins_count(self) -> int:
        """Количество загруженных плагинов"""
        return len(self._plugins)


# Глобальный экземпляр Plugin Manager
plugin_manager = PluginManager()
