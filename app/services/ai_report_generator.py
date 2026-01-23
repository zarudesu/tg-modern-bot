"""
AI Report Generator - генерация отчётов для клиентов с помощью AI

Использует OpenAI/Anthropic для создания профессиональных отчётов
на основе данных задачи из Plane (название, описание, комментарии).
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from ..core.ai.ai_manager import ai_manager
from ..utils.logger import bot_logger
from ..config import settings


@dataclass
class ReportContext:
    """Контекст для генерации отчёта"""
    task_title: str
    task_description: Optional[str]
    comments: List[str]
    company_name: str
    workers: List[str]
    duration_minutes: Optional[int] = None
    travel_type: Optional[str] = None  # "office", "remote", "onsite"


@dataclass
class GeneratedReport:
    """Результат генерации отчёта"""
    summary: str  # Краткое описание выполненных работ
    details: Optional[str]  # Развёрнутое описание (если нужно)
    recommendations: Optional[str]  # Рекомендации клиенту
    success: bool
    error: Optional[str] = None


class AIReportGenerator:
    """
    AI-генератор отчётов для клиентов

    Использует глобальный ai_manager для обращения к LLM.
    Генерирует краткие и профессиональные отчёты на русском языке.
    """

    # Системный промпт для генерации отчётов
    SYSTEM_PROMPT = """Ты - профессиональный IT-специалист, который пишет отчёты для клиентов о выполненных работах.

Твоя задача - на основе данных о задаче (название, описание, комментарии) создать краткий и понятный отчёт.

ПРАВИЛА:
1. Пиши на русском языке
2. Будь кратким, но информативным (2-4 предложения)
3. Используй профессиональный, но понятный клиенту язык
4. НЕ используй технический жаргон без необходимости
5. Фокусируйся на результате для клиента, а не на технических деталях
6. Если в комментариях есть важная информация для клиента - включи её
7. НЕ выдумывай информацию, которой нет в исходных данных

ФОРМАТ ОТВЕТА:
Только текст отчёта, без заголовков, маркеров списков и форматирования.
Просто 2-4 предложения о выполненной работе."""

    DETAILED_PROMPT = """Ты - профессиональный IT-специалист, который пишет подробные отчёты для клиентов.

На основе данных о задаче создай развёрнутый отчёт с рекомендациями.

ПРАВИЛА:
1. Пиши на русском языке
2. Структура: Выполненные работы → Результат → Рекомендации
3. Используй понятный клиенту язык
4. Если есть важные замечания из комментариев - включи их
5. НЕ выдумывай информацию

ФОРМАТ ОТВЕТА (JSON):
{
    "summary": "Краткое описание (2-3 предложения)",
    "details": "Подробное описание работ (3-5 предложений)",
    "recommendations": "Рекомендации клиенту (если есть) или null"
}"""

    async def generate_summary(
        self,
        context: ReportContext,
        detailed: bool = False
    ) -> GeneratedReport:
        """
        Генерировать отчёт на основе контекста задачи

        Args:
            context: Контекст задачи (название, описание, комментарии)
            detailed: Генерировать подробный отчёт с рекомендациями

        Returns:
            GeneratedReport с текстом отчёта или ошибкой
        """
        # Проверяем, есть ли AI провайдер
        provider = ai_manager.get_provider()
        if not provider:
            bot_logger.warning("AI report generation skipped: no AI provider configured")
            return GeneratedReport(
                summary="",
                details=None,
                recommendations=None,
                success=False,
                error="AI не настроен. Добавьте OPENAI_API_KEY в конфигурацию."
            )

        try:
            # Формируем контекст для AI
            user_message = self._build_context_message(context)

            # Выбираем промпт
            system_prompt = self.DETAILED_PROMPT if detailed else self.SYSTEM_PROMPT

            # Генерируем отчёт
            response = await ai_manager.chat(
                user_message=user_message,
                system_prompt=system_prompt
            )

            if not response or not response.content:
                return GeneratedReport(
                    summary="",
                    details=None,
                    recommendations=None,
                    success=False,
                    error="AI вернул пустой ответ"
                )

            # Парсим ответ
            if detailed:
                return self._parse_detailed_response(response.content)
            else:
                return GeneratedReport(
                    summary=response.content.strip(),
                    details=None,
                    recommendations=None,
                    success=True
                )

        except Exception as e:
            bot_logger.error(f"AI report generation failed: {e}")
            return GeneratedReport(
                summary="",
                details=None,
                recommendations=None,
                success=False,
                error=f"Ошибка генерации: {str(e)}"
            )

    def _build_context_message(self, context: ReportContext) -> str:
        """Построить сообщение для AI из контекста задачи"""
        parts = []

        # Компания и исполнители
        parts.append(f"КОМПАНИЯ: {context.company_name}")
        if context.workers:
            parts.append(f"ИСПОЛНИТЕЛИ: {', '.join(context.workers)}")

        # Название задачи
        parts.append(f"\nЗАДАЧА: {context.task_title}")

        # Описание
        if context.task_description:
            # Обрезаем слишком длинные описания
            desc = context.task_description[:2000]
            parts.append(f"\nОПИСАНИЕ:\n{desc}")

        # Комментарии (последние 5)
        if context.comments:
            comments_text = "\n".join(f"- {c[:500]}" for c in context.comments[-5:])
            parts.append(f"\nКОММЕНТАРИИ:\n{comments_text}")

        # Дополнительная информация
        if context.duration_minutes:
            hours = context.duration_minutes // 60
            mins = context.duration_minutes % 60
            if hours > 0:
                parts.append(f"\nВРЕМЯ РАБОТЫ: {hours} ч. {mins} мин.")
            else:
                parts.append(f"\nВРЕМЯ РАБОТЫ: {mins} мин.")

        if context.travel_type:
            travel_map = {
                "office": "в офисе",
                "remote": "удалённо",
                "onsite": "на выезде"
            }
            parts.append(f"ТИП РАБОТЫ: {travel_map.get(context.travel_type, context.travel_type)}")

        return "\n".join(parts)

    def _parse_detailed_response(self, content: str) -> GeneratedReport:
        """Парсить JSON ответ для подробного отчёта"""
        import json

        try:
            # Пытаемся распарсить как JSON
            # Ищем JSON в ответе (может быть в markdown блоке)
            content = content.strip()
            if content.startswith("```"):
                # Убираем markdown блоки
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            data = json.loads(content)

            return GeneratedReport(
                summary=data.get("summary", ""),
                details=data.get("details"),
                recommendations=data.get("recommendations"),
                success=True
            )

        except json.JSONDecodeError:
            # Если не JSON, используем весь текст как summary
            return GeneratedReport(
                summary=content[:500],
                details=None,
                recommendations=None,
                success=True
            )


# Глобальный экземпляр генератора отчётов
ai_report_generator = AIReportGenerator()
