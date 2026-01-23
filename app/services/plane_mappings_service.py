"""
Сервис для работы с маппингами Plane → Telegram

Заменяет hardcoded PLANE_TO_TELEGRAM_MAP и COMPANY_MAPPING
из task_reports_service.py на динамические запросы к БД с кэшированием.
"""
import asyncio
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.plane_mappings_models import PlaneTelegramMapping, CompanyMapping
from ..utils.logger import bot_logger


@dataclass
class TelegramUserInfo:
    """Информация о Telegram пользователе"""
    telegram_id: int
    telegram_username: Optional[str]
    display_name: Optional[str]
    short_name: Optional[str] = None      # Короткое имя для UI (Костя)
    group_handle: Optional[str] = None    # @handle для групповых сообщений


@dataclass
class CompanyInfo:
    """Информация о компании"""
    plane_project_name: str
    display_name_ru: str
    display_name_en: Optional[str]
    client_chat_id: Optional[int]


class PlaneMappingsService:
    """
    Сервис для маппинга Plane пользователей на Telegram

    Использует in-memory кэш с TTL для минимизации запросов к БД.
    Кэш автоматически инвалидируется через 5 минут.
    """

    # Кэш для маппингов (shared across instances)
    _telegram_cache: Dict[str, TelegramUserInfo] = {}
    _company_cache: Dict[str, CompanyInfo] = {}
    _cache_timestamp: Optional[datetime] = None
    _cache_ttl_minutes: int = 5
    _cache_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_telegram_info(self, plane_identifier: str) -> Optional[TelegramUserInfo]:
        """
        Получить Telegram информацию по идентификатору Plane

        Args:
            plane_identifier: Имя, email или username из Plane

        Returns:
            TelegramUserInfo или None если маппинг не найден
        """
        # Нормализуем ключ
        lookup_key = plane_identifier.strip()

        # Проверяем кэш
        await self._ensure_cache_valid()

        if lookup_key in self._telegram_cache:
            return self._telegram_cache[lookup_key]

        # Пробуем найти в БД (case-insensitive)
        result = await self.session.execute(
            select(PlaneTelegramMapping)
            .where(PlaneTelegramMapping.lookup_key.ilike(lookup_key))
            .where(PlaneTelegramMapping.is_active == True)
        )
        mapping = result.scalar_one_or_none()

        if mapping:
            info = TelegramUserInfo(
                telegram_id=mapping.telegram_id,
                telegram_username=mapping.telegram_username,
                display_name=mapping.display_name,
                short_name=mapping.short_name,
                group_handle=mapping.group_handle
            )
            # Добавляем в кэш
            self._telegram_cache[lookup_key] = info
            return info

        bot_logger.debug(f"No Plane→Telegram mapping found for: {lookup_key}")
        return None

    async def get_telegram_id(self, plane_identifier: str) -> Optional[int]:
        """Получить только Telegram ID по идентификатору Plane"""
        info = await self.get_telegram_info(plane_identifier)
        return info.telegram_id if info else None

    async def get_by_telegram_username(self, telegram_username: str) -> Optional[TelegramUserInfo]:
        """
        Получить информацию по telegram username

        Args:
            telegram_username: Username в Telegram (без @)

        Returns:
            TelegramUserInfo или None
        """
        username = telegram_username.strip().lower().lstrip('@')

        await self._ensure_cache_valid()

        # Ищем в кэше по telegram_username
        for info in self._telegram_cache.values():
            if info.telegram_username and info.telegram_username.lower() == username:
                return info

        # Fallback: ищем в БД
        result = await self.session.execute(
            select(PlaneTelegramMapping)
            .where(PlaneTelegramMapping.telegram_username.ilike(username))
            .where(PlaneTelegramMapping.is_active == True)
        )
        mapping = result.scalar_one_or_none()

        if mapping:
            return TelegramUserInfo(
                telegram_id=mapping.telegram_id,
                telegram_username=mapping.telegram_username,
                display_name=mapping.display_name,
                short_name=mapping.short_name,
                group_handle=mapping.group_handle
            )

        return None

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[TelegramUserInfo]:
        """
        Получить информацию по telegram_id

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            TelegramUserInfo или None
        """
        await self._ensure_cache_valid()

        # Ищем в кэше
        for info in self._telegram_cache.values():
            if info.telegram_id == telegram_id:
                return info

        # Fallback: ищем в БД
        result = await self.session.execute(
            select(PlaneTelegramMapping)
            .where(PlaneTelegramMapping.telegram_id == telegram_id)
            .where(PlaneTelegramMapping.is_active == True)
        )
        mapping = result.first()

        if mapping:
            m = mapping[0]
            return TelegramUserInfo(
                telegram_id=m.telegram_id,
                telegram_username=m.telegram_username,
                display_name=m.display_name,
                short_name=m.short_name,
                group_handle=m.group_handle
            )

        return None

    async def get_short_name(self, telegram_username: str) -> str:
        """Получить короткое имя по username (или username если не найдено)"""
        info = await self.get_by_telegram_username(telegram_username)
        if info and info.short_name:
            return info.short_name
        return telegram_username

    async def get_group_handle(self, telegram_username: str) -> str:
        """Получить @handle для группы по username (или @username если не найдено)"""
        info = await self.get_by_telegram_username(telegram_username)
        if info and info.group_handle:
            return info.group_handle
        return f"@{telegram_username}"

    async def get_company_info(self, plane_project_name: str) -> Optional[CompanyInfo]:
        """
        Получить информацию о компании по названию проекта Plane

        Args:
            plane_project_name: Название проекта в Plane (e.g., "HHIVP", "DELTA")

        Returns:
            CompanyInfo или None если маппинг не найден
        """
        lookup_key = plane_project_name.strip().upper()

        await self._ensure_cache_valid()

        if lookup_key in self._company_cache:
            return self._company_cache[lookup_key]

        # Ищем в БД
        result = await self.session.execute(
            select(CompanyMapping)
            .where(CompanyMapping.plane_project_name.ilike(lookup_key))
            .where(CompanyMapping.is_active == True)
        )
        mapping = result.scalar_one_or_none()

        if mapping:
            info = CompanyInfo(
                plane_project_name=mapping.plane_project_name,
                display_name_ru=mapping.display_name_ru,
                display_name_en=mapping.display_name_en,
                client_chat_id=mapping.client_chat_id
            )
            self._company_cache[lookup_key] = info
            return info

        bot_logger.debug(f"No company mapping found for: {plane_project_name}")
        return None

    async def get_company_display_name(self, plane_project_name: str) -> str:
        """Получить русское название компании (или оригинал если не найдено)"""
        info = await self.get_company_info(plane_project_name)
        return info.display_name_ru if info else plane_project_name

    async def _ensure_cache_valid(self):
        """Проверить валидность кэша и обновить при необходимости"""
        async with self._cache_lock:
            if self._cache_timestamp is None:
                await self._refresh_cache()
            elif datetime.now() - self._cache_timestamp > timedelta(minutes=self._cache_ttl_minutes):
                await self._refresh_cache()

    async def _refresh_cache(self):
        """Обновить кэш из БД"""
        try:
            # Загружаем все telegram mappings
            result = await self.session.execute(
                select(PlaneTelegramMapping)
                .where(PlaneTelegramMapping.is_active == True)
            )
            mappings = result.scalars().all()

            self._telegram_cache.clear()
            for m in mappings:
                self._telegram_cache[m.lookup_key] = TelegramUserInfo(
                    telegram_id=m.telegram_id,
                    telegram_username=m.telegram_username,
                    display_name=m.display_name,
                    short_name=m.short_name,
                    group_handle=m.group_handle
                )

            # Загружаем все company mappings
            result = await self.session.execute(
                select(CompanyMapping)
                .where(CompanyMapping.is_active == True)
            )
            companies = result.scalars().all()

            self._company_cache.clear()
            for c in companies:
                self._company_cache[c.plane_project_name.upper()] = CompanyInfo(
                    plane_project_name=c.plane_project_name,
                    display_name_ru=c.display_name_ru,
                    display_name_en=c.display_name_en,
                    client_chat_id=c.client_chat_id
                )

            self._cache_timestamp = datetime.now()
            bot_logger.info(
                f"Plane mappings cache refreshed: "
                f"{len(self._telegram_cache)} telegram, {len(self._company_cache)} companies"
            )

        except Exception as e:
            bot_logger.error(f"Failed to refresh plane mappings cache: {e}")

    @classmethod
    def invalidate_cache(cls):
        """Принудительная инвалидация кэша (вызывать после изменений в БД)"""
        cls._cache_timestamp = None
        cls._telegram_cache.clear()
        cls._company_cache.clear()
        bot_logger.info("Plane mappings cache invalidated")

    # === CRUD методы для админов ===

    async def add_telegram_mapping(
        self,
        lookup_key: str,
        telegram_id: int,
        telegram_username: Optional[str] = None,
        display_name: Optional[str] = None,
        short_name: Optional[str] = None,
        group_handle: Optional[str] = None,
        plane_email: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> PlaneTelegramMapping:
        """Добавить новый маппинг Plane→Telegram"""
        mapping = PlaneTelegramMapping(
            lookup_key=lookup_key.strip(),
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            display_name=display_name,
            short_name=short_name,
            group_handle=group_handle,
            plane_email=plane_email,
            created_by=created_by
        )
        self.session.add(mapping)
        await self.session.commit()
        self.invalidate_cache()
        bot_logger.info(f"Added Plane→Telegram mapping: {lookup_key} → {telegram_id}")
        return mapping

    async def add_company_mapping(
        self,
        plane_project_name: str,
        display_name_ru: str,
        display_name_en: Optional[str] = None,
        plane_project_id: Optional[str] = None,
        client_chat_id: Optional[int] = None
    ) -> CompanyMapping:
        """Добавить новый маппинг компании"""
        mapping = CompanyMapping(
            plane_project_name=plane_project_name.strip(),
            display_name_ru=display_name_ru,
            display_name_en=display_name_en,
            plane_project_id=plane_project_id,
            client_chat_id=client_chat_id
        )
        self.session.add(mapping)
        await self.session.commit()
        self.invalidate_cache()
        bot_logger.info(f"Added company mapping: {plane_project_name} → {display_name_ru}")
        return mapping

    async def list_telegram_mappings(self) -> List[PlaneTelegramMapping]:
        """Получить все активные telegram маппинги"""
        result = await self.session.execute(
            select(PlaneTelegramMapping)
            .where(PlaneTelegramMapping.is_active == True)
            .order_by(PlaneTelegramMapping.display_name, PlaneTelegramMapping.lookup_key)
        )
        return list(result.scalars().all())

    async def list_company_mappings(self) -> List[CompanyMapping]:
        """Получить все активные company маппинги"""
        result = await self.session.execute(
            select(CompanyMapping)
            .where(CompanyMapping.is_active == True)
            .order_by(CompanyMapping.display_name_ru)
        )
        return list(result.scalars().all())
