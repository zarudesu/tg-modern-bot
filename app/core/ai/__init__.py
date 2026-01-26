"""
AI Abstractions - универсальный слой для работы с LLM

Поддерживает: OpenAI, Anthropic Claude, Groq (Llama), OpenRouter
"""
from .base import AIProvider, AIMessage, AIResponse, AIConfig
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .groq_provider import GroqProvider
from .ai_manager import AIManager, ai_manager

__all__ = [
    'AIProvider',
    'AIMessage',
    'AIResponse',
    'AIConfig',
    'OpenAIProvider',
    'AnthropicProvider',
    'GroqProvider',
    'AIManager',
    'ai_manager'
]
