"""
Gemini Provider - интеграция с Google AI Studio (Gemini API)

Google Gemini — большой контекст (до 1M токенов), бесплатный tier.
Использует OpenAI-совместимый эндпоинт.
"""
import time
from typing import List, AsyncGenerator
import aiohttp

from .base import AIProvider, AIMessage, AIResponse, AIConfig
from ...utils.logger import bot_logger


GEMINI_MODELS = [
    "gemini-2.0-flash",          # Быстрая, 1M контекст
    "gemini-2.0-flash-lite",     # Самая быстрая
    "gemini-1.5-pro",            # Лучшая для сложных задач, 2M контекст
    "gemini-1.5-flash",          # Баланс скорость/качество
]


class GeminiProvider(AIProvider):
    """
    Провайдер для Google Gemini (AI Studio)

    Бесплатный tier: 15 RPM / 1M TPM для flash, 2 RPM для pro.
    Огромный контекст: до 1M (flash) / 2M (pro) токенов.
    """

    API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

    @property
    def provider_name(self) -> str:
        return "Gemini"

    @property
    def supported_models(self) -> List[str]:
        return GEMINI_MODELS

    async def complete(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Получить ответ от Gemini"""
        start_time = time.time()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": kwargs.get("model", self.config.model),
            "messages": [msg.to_dict() for msg in messages],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    bot_logger.error(f"Gemini API error: {error_text}")
                    raise Exception(f"Gemini API error: {response.status}")

                data = await response.json()

                processing_time = time.time() - start_time

                usage = data.get("usage", {})
                return AIResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=data.get("model", self.config.model),
                    tokens_used=usage.get("total_tokens", 0),
                    finish_reason=data["choices"][0].get("finish_reason", "stop"),
                    processing_time=processing_time,
                    metadata={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "gemini_id": data.get("id")
                    }
                )

    async def complete_stream(self, messages: List[AIMessage], **kwargs) -> AsyncGenerator[str, None]:
        """Потоковая генерация от Gemini"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": kwargs.get("model", self.config.model),
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
