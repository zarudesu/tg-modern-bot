"""
AI Manager - центральное управление AI провайдерами
"""
from typing import Dict, Optional, List
from enum import Enum

from .base import AIProvider, AIMessage, AIResponse, AIConfig
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .openrouter_provider import OpenRouterProvider, FREE_MODELS, RECOMMENDED_MODELS
from .groq_provider import GroqProvider, GROQ_MODELS
from .gemini_provider import GeminiProvider, GEMINI_MODELS
from ...utils.logger import bot_logger


class AIProviderType(Enum):
    """Типы AI провайдеров"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    GROQ = "groq"
    GEMINI = "gemini"
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

    def create_openrouter_provider(
        self,
        api_key: str,
        model: str = None,
        name: str = "openrouter",
        set_as_default: bool = False,
        site_url: str = None,
        site_name: str = None,
        **config_kwargs
    ) -> OpenRouterProvider:
        """
        Создать и зарегистрировать OpenRouter провайдер

        OpenRouter даёт доступ к множеству моделей через единый API,
        включая бесплатные (Llama, Gemma, Mistral, Qwen).

        Args:
            api_key: OpenRouter API ключ (получить на openrouter.ai)
            model: Модель (по умолчанию бесплатная Llama 3.2)
            name: Имя провайдера
            set_as_default: Установить как default
            site_url: URL вашего сайта/приложения
            site_name: Название приложения
            **config_kwargs: Дополнительные параметры конфигурации

        Returns:
            Созданный OpenRouter провайдер
        """
        # Если модель не указана, используем бесплатную
        if model is None:
            model = FREE_MODELS[0]  # meta-llama/llama-3.2-3b-instruct:free

        config = AIConfig(model=model, **config_kwargs)
        provider = OpenRouterProvider(
            api_key=api_key,
            config=config,
            site_url=site_url,
            site_name=site_name
        )

        self.register_provider(name, provider, set_as_default)
        return provider

    def create_groq_provider(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        name: str = "groq",
        set_as_default: bool = False,
        **config_kwargs
    ) -> GroqProvider:
        """
        Создать и зарегистрировать Groq провайдер

        Groq - очень быстрый LLM inference (LPU).
        Бесплатный tier: ~14,400 requests/day.

        Args:
            api_key: Groq API ключ
            model: Модель (llama-3.3-70b-versatile, llama-3.1-8b-instant, etc)
            name: Имя провайдера
            set_as_default: Установить как default
            **config_kwargs: Дополнительные параметры конфигурации

        Returns:
            Созданный Groq провайдер
        """
        config = AIConfig(model=model, **config_kwargs)
        provider = GroqProvider(api_key=api_key, config=config)

        self.register_provider(name, provider, set_as_default)
        return provider

    def create_gemini_provider(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        name: str = "gemini",
        set_as_default: bool = False,
        **config_kwargs
    ) -> GeminiProvider:
        """
        Создать и зарегистрировать Google Gemini провайдер

        Gemini — большой контекст (до 1M токенов), бесплатный tier.

        Args:
            api_key: Google AI Studio API ключ
            model: Модель (gemini-2.0-flash, gemini-1.5-pro, etc)
            name: Имя провайдера
            set_as_default: Установить как default
            **config_kwargs: Дополнительные параметры конфигурации

        Returns:
            Созданный Gemini провайдер
        """
        config = AIConfig(model=model, **config_kwargs)
        provider = GeminiProvider(api_key=api_key, config=config)

        self.register_provider(name, provider, set_as_default)
        return provider

    @staticmethod
    def get_gemini_models() -> list:
        """Получить список моделей Gemini"""
        return GEMINI_MODELS.copy()

    @staticmethod
    def get_groq_models() -> list:
        """Получить список моделей Groq"""
        return GROQ_MODELS.copy()

    @staticmethod
    def get_free_models() -> list:
        """Получить список бесплатных моделей OpenRouter"""
        return FREE_MODELS.copy()

    @staticmethod
    def get_recommended_model(task: str) -> str:
        """
        Получить рекомендуемую бесплатную модель для задачи

        Args:
            task: Тип задачи (chat, task_detection, report_generation, code)

        Returns:
            Название модели OpenRouter
        """
        return RECOMMENDED_MODELS.get(task, RECOMMENDED_MODELS.get("chat"))

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
