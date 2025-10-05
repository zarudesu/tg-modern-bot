"""
AI Manager - центральное управление AI провайдерами
"""
from typing import Dict, Optional, List
from enum import Enum

from .base import AIProvider, AIMessage, AIResponse, AIConfig
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from ...utils.logger import bot_logger


class AIProviderType(Enum):
    """Типы AI провайдеров"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


class AIManager:
    """
    AI Manager - управление всеми AI провайдерами

    Singleton для централизованной работы с разными LLM
    """
    _instance = None
    _providers: Dict[str, AIProvider] = {}
    _default_provider: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register_provider(
        self,
        name: str,
        provider: AIProvider,
        set_as_default: bool = False
    ):
        """
        Регистрация AI провайдера

        Args:
            name: Уникальное имя провайдера
            provider: Экземпляр AI провайдера
            set_as_default: Установить как провайдер по умолчанию
        """
        self._providers[name] = provider

        if set_as_default or not self._default_provider:
            self._default_provider = name

        bot_logger.info(
            f"AI Provider registered: {name}",
            extra={
                "provider_type": provider.provider_name,
                "model": provider.config.model,
                "is_default": set_as_default or not self._default_provider
            }
        )

    def create_openai_provider(
        self,
        api_key: str,
        model: str = "gpt-4-turbo",
        name: str = "openai",
        set_as_default: bool = False,
        **config_kwargs
    ) -> OpenAIProvider:
        """
        Создать и зарегистрировать OpenAI провайдер

        Args:
            api_key: OpenAI API ключ
            model: Модель (gpt-4, gpt-3.5-turbo, etc)
            name: Имя провайдера
            set_as_default: Установить как default
            **config_kwargs: Дополнительные параметры конфигурации

        Returns:
            Созданный OpenAI провайдер
        """
        config = AIConfig(model=model, **config_kwargs)
        provider = OpenAIProvider(api_key=api_key, config=config)

        self.register_provider(name, provider, set_as_default)
        return provider

    def create_anthropic_provider(
        self,
        api_key: str,
        model: str = "claude-3-sonnet-20240229",
        name: str = "anthropic",
        set_as_default: bool = False,
        **config_kwargs
    ) -> AnthropicProvider:
        """
        Создать и зарегистрировать Anthropic провайдер

        Args:
            api_key: Anthropic API ключ
            model: Модель (claude-3-opus, claude-3-sonnet, etc)
            name: Имя провайдера
            set_as_default: Установить как default
            **config_kwargs: Дополнительные параметры конфигурации

        Returns:
            Созданный Anthropic провайдер
        """
        config = AIConfig(model=model, **config_kwargs)
        provider = AnthropicProvider(api_key=api_key, config=config)

        self.register_provider(name, provider, set_as_default)
        return provider

    def get_provider(self, name: Optional[str] = None) -> Optional[AIProvider]:
        """
        Получить провайдер по имени

        Args:
            name: Имя провайдера (если None, возвращает default)

        Returns:
            AI провайдер или None
        """
        if name is None:
            name = self._default_provider

        return self._providers.get(name) if name else None

    def set_default_provider(self, name: str):
        """Установить провайдер по умолчанию"""
        if name not in self._providers:
            raise ValueError(f"Provider {name} not found")

        self._default_provider = name
        bot_logger.info(f"Default AI provider set to: {name}")

    async def complete(
        self,
        messages: List[AIMessage],
        provider_name: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        """
        Получить ответ от AI

        Args:
            messages: История сообщений
            provider_name: Имя провайдера (если None, использует default)
            **kwargs: Дополнительные параметры

        Returns:
            AIResponse с ответом
        """
        provider = self.get_provider(provider_name)

        if not provider:
            raise ValueError(
                f"No AI provider available. "
                f"Provider: {provider_name or 'default'}"
            )

        return await provider.complete(messages, **kwargs)

    async def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        """
        Простой чат с AI

        Args:
            user_message: Сообщение пользователя
            system_prompt: Системный промпт
            provider_name: Имя провайдера
            **kwargs: Дополнительные параметры

        Returns:
            AIResponse с ответом
        """
        provider = self.get_provider(provider_name)

        if not provider:
            raise ValueError(
                f"No AI provider available. "
                f"Provider: {provider_name or 'default'}"
            )

        return await provider.chat(user_message, system_prompt, **kwargs)

    def list_providers(self) -> List[Dict[str, any]]:
        """
        Получить список всех провайдеров

        Returns:
            Список с информацией о провайдерах
        """
        providers_info = []

        for name, provider in self._providers.items():
            providers_info.append({
                "name": name,
                "type": provider.provider_name,
                "model": provider.config.model,
                "is_default": name == self._default_provider
            })

        return providers_info

    def remove_provider(self, name: str):
        """Удалить провайдер"""
        if name in self._providers:
            del self._providers[name]

            if self._default_provider == name:
                self._default_provider = next(iter(self._providers), None)

            bot_logger.info(f"AI Provider removed: {name}")

    @property
    def default_provider_name(self) -> Optional[str]:
        """Имя провайдера по умолчанию"""
        return self._default_provider

    @property
    def providers_count(self) -> int:
        """Количество зарегистрированных провайдеров"""
        return len(self._providers)


# Глобальный экземпляр AI Manager
ai_manager = AIManager()
