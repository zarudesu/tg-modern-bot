"""
Groq Provider - интеграция с Groq API (Llama, Mixtral, Gemma)

Groq - очень быстрый LLM inference с бесплатным tier.
API совместим с OpenAI.
"""
import time
from typing import List, AsyncGenerator
import aiohttp

from .base import AIProvider, AIMessage, AIResponse, AIConfig
from ...utils.logger import bot_logger


# Доступные модели Groq (январь 2026)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",      # Лучшая для сложных задач
    "llama-3.1-8b-instant",          # Быстрая, хорошая для чата
    "llama-3.2-3b-preview",          # Самая быстрая
    "mixtral-8x7b-32768",            # Хороша для длинного контекста
    "gemma2-9b-it",                  # Google Gemma
]


class GroqProvider(AIProvider):
    """
    Провайдер для Groq (Llama, Mixtral, Gemma)

    Groq предоставляет очень быстрый inference благодаря LPU.
    Бесплатный tier: 14,400 requests/day для llama-3.1-8b
    """

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "Groq"

    @property
    def supported_models(self) -> List[str]:
        return GROQ_MODELS

    async def complete(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Получить ответ от Groq"""
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
                    bot_logger.error(f"Groq API error: {error_text}")
                    raise Exception(f"Groq API error: {response.status}")

                data = await response.json()

                processing_time = time.time() - start_time

                return AIResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=data["model"],
                    tokens_used=data["usage"]["total_tokens"],
                    finish_reason=data["choices"][0]["finish_reason"],
                    processing_time=processing_time,
                    metadata={
                        "prompt_tokens": data["usage"]["prompt_tokens"],
                        "completion_tokens": data["usage"]["completion_tokens"],
                        "groq_id": data.get("id")
                    }
                )

    async def complete_stream(self, messages: List[AIMessage], **kwargs) -> AsyncGenerator[str, None]:
        """Потоковая генерация от Groq"""
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
