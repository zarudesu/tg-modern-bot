"""
Anthropic Provider - интеграция с Claude API
"""
import time
from typing import List, AsyncGenerator
import aiohttp

from .base import AIProvider, AIMessage, AIResponse, AIConfig, AIRole
from ...utils.logger import bot_logger


class AnthropicProvider(AIProvider):
    """Провайдер для Anthropic Claude"""

    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    @property
    def supported_models(self) -> List[str]:
        return [
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
            "claude-2.1",
            "claude-2.0"
        ]

    def _prepare_messages(self, messages: List[AIMessage]) -> tuple:
        """Подготовить сообщения для Anthropic API"""
        system_prompt = None
        api_messages = []

        for msg in messages:
            if msg.role == AIRole.SYSTEM:
                system_prompt = msg.content
            else:
                api_messages.append({
                    "role": msg.role.value,
                    "content": msg.content
                })

        return system_prompt, api_messages

    async def complete(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Получить ответ от Claude"""
        start_time = time.time()

        system_prompt, api_messages = self._prepare_messages(messages)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json"
        }

        payload = {
            "model": kwargs.get("model", self.config.model),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": api_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        if system_prompt:
            payload["system"] = system_prompt

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    bot_logger.error(f"Anthropic API error: {error_text}")
                    raise Exception(f"Anthropic API error: {response.status}")

                data = await response.json()

                processing_time = time.time() - start_time

                # Claude возвращает контент в виде массива блоков
                content = data["content"][0]["text"] if data["content"] else ""

                return AIResponse(
                    content=content,
                    model=data["model"],
                    tokens_used=data["usage"]["input_tokens"] + data["usage"]["output_tokens"],
                    finish_reason=data.get("stop_reason", "end_turn"),
                    processing_time=processing_time,
                    metadata={
                        "input_tokens": data["usage"]["input_tokens"],
                        "output_tokens": data["usage"]["output_tokens"]
                    }
                )

    async def complete_stream(self, messages: List[AIMessage], **kwargs) -> AsyncGenerator[str, None]:
        """Потоковая генерация от Claude"""
        system_prompt, api_messages = self._prepare_messages(messages)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json"
        }

        payload = {
            "model": kwargs.get("model", self.config.model),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": api_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": True
        }

        if system_prompt:
            payload["system"] = system_prompt

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

                    if not line:
                        continue

                    try:
                        import json
                        data = json.loads(line)

                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta", {})
                            text = delta.get("text", "")

                            if text:
                                yield text

                    except json.JSONDecodeError:
                        continue
