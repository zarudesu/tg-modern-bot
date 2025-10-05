"""
OpenAI Provider - интеграция с OpenAI API (GPT-4, GPT-3.5, etc)
"""
import time
from typing import List, AsyncGenerator
import aiohttp

from .base import AIProvider, AIMessage, AIResponse, AIConfig
from ...utils.logger import bot_logger


class OpenAIProvider(AIProvider):
    """Провайдер для OpenAI (GPT-4, GPT-3.5-turbo)"""

    API_URL = "https://api.openai.com/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    @property
    def supported_models(self) -> List[str]:
        return [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4-vision",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ]

    async def complete(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Получить ответ от OpenAI"""
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
            "frequency_penalty": kwargs.get("frequency_penalty", self.config.frequency_penalty),
            "presence_penalty": kwargs.get("presence_penalty", self.config.presence_penalty)
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
                    bot_logger.error(f"OpenAI API error: {error_text}")
                    raise Exception(f"OpenAI API error: {response.status}")

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
                        "completion_tokens": data["usage"]["completion_tokens"]
                    }
                )

    async def complete_stream(self, messages: List[AIMessage], **kwargs) -> AsyncGenerator[str, None]:
        """Потоковая генерация от OpenAI"""
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
                        line = line[6:]  # Remove "data: " prefix

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
