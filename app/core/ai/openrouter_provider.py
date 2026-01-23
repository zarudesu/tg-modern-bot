"""
OpenRouter Provider - единый API для множества LLM моделей

OpenRouter предоставляет доступ к:
- Бесплатным моделям (Llama, Gemma, Qwen, Mistral)
- Платным моделям (GPT-4, Claude, etc.)

API совместим с OpenAI, но через другой endpoint.
"""
import time
from typing import List, AsyncGenerator, Optional
import aiohttp

from .base import AIProvider, AIMessage, AIResponse, AIConfig
from ...utils.logger import bot_logger


# Бесплатные модели на OpenRouter (лимиты могут меняться)
FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "google/gemma-2-9b-it:free",
    "qwen/qwen-2-7b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "huggingfaceh4/zephyr-7b-beta:free",
]

# Рекомендуемые модели по задачам
RECOMMENDED_MODELS = {
    "chat": "meta-llama/llama-3.1-8b-instruct:free",  # Хороший баланс
    "task_detection": "mistralai/mistral-7b-instruct:free",  # Быстрый
    "report_generation": "google/gemma-2-9b-it:free",  # Качественный текст
    "code": "qwen/qwen-2-7b-instruct:free",  # Хорош для кода
}


class OpenRouterProvider(AIProvider):
    """
    Провайдер для OpenRouter - единый API для всех LLM

    Поддерживает:
    - Бесплатные модели (с лимитами)
    - Платные модели (GPT-4, Claude, etc.)
    - Автоматический fallback между моделями
    """

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        config: Optional[AIConfig] = None,
        site_url: Optional[str] = None,
        site_name: Optional[str] = None
    ):
        """
        Args:
            api_key: OpenRouter API key
            config: AI configuration
            site_url: Your site URL (for OpenRouter rankings)
            site_name: Your app name (shown in OpenRouter dashboard)
        """
        super().__init__(api_key, config)
        self.site_url = site_url or "https://t.me/hhivp_it_bot"
        self.site_name = site_name or "HHIVP IT Bot"

    @property
    def provider_name(self) -> str:
        return "OpenRouter"

    @property
    def supported_models(self) -> List[str]:
        return FREE_MODELS + [
            # Платные модели (если понадобятся)
            "openai/gpt-4-turbo",
            "openai/gpt-4o",
            "openai/gpt-3.5-turbo",
            "anthropic/claude-3-opus",
            "anthropic/claude-3-sonnet",
            "anthropic/claude-3-haiku",
            "google/gemini-pro",
            "meta-llama/llama-3.1-70b-instruct",
        ]

    async def complete(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Получить ответ через OpenRouter"""
        start_time = time.time()

        model = kwargs.get("model", self.config.model)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
        }

        payload = {
            "model": model,
            "messages": [msg.to_dict() for msg in messages],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
        }

        # Для бесплатных моделей добавляем route: fallback
        if ":free" in model:
            payload["route"] = "fallback"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    response_text = await response.text()

                    if response.status != 200:
                        bot_logger.error(f"OpenRouter API error: {response.status} - {response_text}")

                        # Попробуем fallback на другую бесплатную модель
                        if ":free" in model:
                            fallback_model = await self._get_fallback_model(model)
                            if fallback_model:
                                bot_logger.info(f"Trying fallback model: {fallback_model}")
                                return await self.complete(messages, model=fallback_model, **kwargs)

                        raise Exception(f"OpenRouter API error: {response.status}")

                    import json
                    data = json.loads(response_text)

                    processing_time = time.time() - start_time

                    # OpenRouter может вернуть usage или нет
                    usage = data.get("usage", {})

                    return AIResponse(
                        content=data["choices"][0]["message"]["content"],
                        model=data.get("model", model),
                        tokens_used=usage.get("total_tokens", 0),
                        finish_reason=data["choices"][0].get("finish_reason", "stop"),
                        processing_time=processing_time,
                        metadata={
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "provider": "openrouter",
                            "actual_model": data.get("model", model),
                        }
                    )

        except aiohttp.ClientError as e:
            bot_logger.error(f"OpenRouter connection error: {e}")
            raise Exception(f"Connection error: {e}")

    async def complete_stream(self, messages: List[AIMessage], **kwargs) -> AsyncGenerator[str, None]:
        """Потоковая генерация через OpenRouter"""
        model = kwargs.get("model", self.config.model)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
        }

        payload = {
            "model": model,
            "messages": [msg.to_dict() for msg in messages],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "stream": True
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                async for line in response.content:
                    line = line.decode('utf-8').strip()

                    if line.startswith("data: "):
                        line = line[6:]

                    if line == "[DONE]":
                        break

                    if not line:
                        continue

                    try:
                        import json
                        data = json.loads(line)

                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                yield content

                    except json.JSONDecodeError:
                        continue

    async def _get_fallback_model(self, failed_model: str) -> Optional[str]:
        """Получить fallback модель если текущая недоступна"""
        # Исключаем failed модель из списка
        available = [m for m in FREE_MODELS if m != failed_model]
        return available[0] if available else None

    @staticmethod
    def get_recommended_model(task: str) -> str:
        """
        Получить рекомендуемую модель для задачи

        Args:
            task: Тип задачи (chat, task_detection, report_generation, code)

        Returns:
            Название модели
        """
        return RECOMMENDED_MODELS.get(task, RECOMMENDED_MODELS["chat"])


# Хелпер для быстрого создания провайдера
def create_openrouter_provider(
    api_key: str,
    model: str = None,
    **kwargs
) -> OpenRouterProvider:
    """
    Быстрое создание OpenRouter провайдера

    Args:
        api_key: OpenRouter API key (получить на openrouter.ai)
        model: Модель (по умолчанию бесплатная Llama)
        **kwargs: Дополнительные параметры AIConfig

    Returns:
        OpenRouterProvider instance
    """
    if model is None:
        model = FREE_MODELS[0]  # Llama 3.2 3B по умолчанию

    config = AIConfig(
        model=model,
        temperature=kwargs.get("temperature", 0.7),
        max_tokens=kwargs.get("max_tokens", 1500),
        timeout=kwargs.get("timeout", 60),
    )

    return OpenRouterProvider(
        api_key=api_key,
        config=config,
        site_url=kwargs.get("site_url"),
        site_name=kwargs.get("site_name"),
    )
