"""
Базовые абстракции для AI провайдеров
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncGenerator
from enum import Enum
from datetime import datetime


class AIRole(Enum):
    """Роли в диалоге с AI"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class AIMessage:
    """Сообщение в диалоге с AI"""
    role: AIRole
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, str]:
        """Конвертация в словарь для API"""
        return {
            "role": self.role.value,
            "content": self.content
        }


@dataclass
class AIResponse:
    """Ответ от AI"""
    content: str
    model: str
    tokens_used: int
    finish_reason: str
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def cost_estimate(self) -> float:
        """Примерная стоимость запроса (в USD)"""
        # Примерные цены (нужно обновлять)
        costs_per_1k = {
            "gpt-4": 0.03,
            "gpt-4-turbo": 0.01,
            "gpt-3.5-turbo": 0.0015,
            "claude-3-opus": 0.015,
            "claude-3-sonnet": 0.003,
            "claude-3-haiku": 0.00025
        }

        for model_prefix, cost in costs_per_1k.items():
            if model_prefix in self.model.lower():
                return (self.tokens_used / 1000) * cost

        return 0.0  # Неизвестная модель


@dataclass
class AIConfig:
    """Конфигурация AI провайдера"""
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    system_prompt: Optional[str] = None
    timeout: int = 60
    retry_attempts: int = 3
    stream: bool = False


class AIProvider(ABC):
    """
    Базовый класс для AI провайдеров

    Поддерживает любые LLM API с единым интерфейсом
    """

    def __init__(self, api_key: str, config: AIConfig):
        self.api_key = api_key
        self.config = config
        self._conversation_history: List[AIMessage] = []

    @abstractmethod
    async def complete(
        self,
        messages: List[AIMessage],
        **kwargs
    ) -> AIResponse:
        """
        Получить ответ от AI

        Args:
            messages: История диалога
            **kwargs: Дополнительные параметры

        Returns:
            AIResponse с ответом
        """
        pass

    @abstractmethod
    async def complete_stream(
        self,
        messages: List[AIMessage],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Потоковая генерация ответа

        Args:
            messages: История диалога
            **kwargs: Дополнительные параметры

        Yields:
            Части ответа по мере генерации
        """
        pass

    async def chat(self, user_message: str, system_prompt: Optional[str] = None) -> AIResponse:
        """
        Простой чат с AI

        Args:
            user_message: Сообщение пользователя
            system_prompt: Системный промпт (опционально)

        Returns:
            AIResponse с ответом
        """
        messages = []

        # Добавляем системный промпт
        if system_prompt or self.config.system_prompt:
            messages.append(AIMessage(
                role=AIRole.SYSTEM,
                content=system_prompt or self.config.system_prompt
            ))

        # Добавляем историю разговора
        messages.extend(self._conversation_history)

        # Добавляем новое сообщение пользователя
        user_msg = AIMessage(role=AIRole.USER, content=user_message)
        messages.append(user_msg)

        # Получаем ответ
        response = await self.complete(messages)

        # Сохраняем в историю
        self._conversation_history.append(user_msg)
        self._conversation_history.append(AIMessage(
            role=AIRole.ASSISTANT,
            content=response.content
        ))

        # Ограничиваем историю (последние 20 сообщений)
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]

        return response

    def clear_history(self):
        """Очистить историю диалога"""
        self._conversation_history.clear()

    def get_history(self) -> List[AIMessage]:
        """Получить историю диалога"""
        return self._conversation_history.copy()

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Название провайдера"""
        pass

    @property
    @abstractmethod
    def supported_models(self) -> List[str]:
        """Поддерживаемые модели"""
        pass

    def validate_model(self, model: str) -> bool:
        """Проверка поддержки модели"""
        return any(m in model for m in self.supported_models)
