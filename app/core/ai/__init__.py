"""
AI Abstractions - универсальный слой для работы с LLM

Поддерживает: OpenAI, Anthropic Claude, Llama, и другие
"""
from .base import AIProvider, AIMessage, AIResponse, AIConfig
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .ai_manager import AIManager, ai_manager

__all__ = [
    'AIProvider',
    'AIMessage',
    'AIResponse',
    'AIConfig',
    'OpenAIProvider',
    'AnthropicProvider',
    'AIManager',
    'ai_manager'
]
