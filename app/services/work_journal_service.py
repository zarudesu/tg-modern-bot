"""
Сервис для работы с журналом работ
"""
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Tuple, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from ..database.models import BotUser
from ..database.work_journal_models import (
    WorkJournalEntry, 
    UserWorkJournalState,
    WorkJournalCompany,
    WorkJournalWorker
)
from ..utils.work_journal_constants import (
    WorkJournalState, 
    N8nSyncStatus,
    DEFAULT_COMPANIES,
    DEFAULT_WORKERS
)
from ..utils.logger import bot_logger


class WorkJournalService:
    """Сервис для работы с журналом работ"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_user_state(self, telegram_user_id: int) -> Optional[UserWorkJournalState]:
        """Получить состояние пользователя"""
        result = await self.session.execute(
            select(UserWorkJournalState)
            .where(UserWorkJournalState.telegram_user_id == telegram_user_id)
        )
        state = result.scalar_one_or_none()
        
        if state:
            # Всегда создаем метод get_draft_workers независимо от содержимого
            if state.draft_workers:
                try:
                    import json
                    # Пытаемся парсить JSON
                    parsed_workers = json.loads(state.draft_workers)
                    object.__setattr__(state, '_parsed_workers', parsed_workers)
                except (json.JSONDecodeError, TypeError):
                    # Если не JSON, делаем список из строки
                    if isinstance(state.draft_workers, str):
                        object.__setattr__(state, '_parsed_workers', [state.draft_workers])
                    else:
                        object.__setattr__(state, '_parsed_workers', [])
            else:
                # Если нет draft_workers, создаем пустой список
                object.__setattr__(state, '_parsed_workers', [])
            
            # Создаем метод для всех случаев
            def get_workers():
                return getattr(state, '_parsed_workers', [])
            state.get_draft_workers = get_workers
        
        return state
    
    async def set_user_state(
        self, 
        telegram_user_id: int, 
        state: WorkJournalState,
        **kwargs
    ) -> UserWorkJournalState:
        """Установить состояние пользователя"""
        
        # Сериализуем draft_workers если это список
        if 'draft_workers' in kwargs and isinstance(kwargs['draft_workers'], list):
            import json
            kwargs['draft_workers'] = json.dumps(kwargs['draft_workers'])
        
        # Проверяем, есть ли уже состояние
        existing_state = await self.get_user_state(telegram_user_id)
        
        if existing_state:
            # Обновляем существующее состояние
            update_data = {"current_state": state.value}
            update_data.update(kwargs)
            
            await self.session.execute(
                update(UserWorkJournalState)
                .where(UserWorkJournalState.telegram_user_id == telegram_user_id)
                .values(**update_data)
            )
            await self.session.commit()
            
            # Получаем обновленное состояние
            return await self.get_user_state(telegram_user_id)
        else:
            # Создаем новое состояние
            new_state = UserWorkJournalState(
                telegram_user_id=telegram_user_id,
                current_state=state.value,
                **kwargs
            )
            self.session.add(new_state)
            await self.session.commit()
            return new_state
    
    async def clear_user_state(self, telegram_user_id: int) -> bool:
        """Очистить состояние пользователя (вернуть в IDLE)"""
        try:
            await self.session.execute(
                update(UserWorkJournalState)
                .where(UserWorkJournalState.telegram_user_id == telegram_user_id)
                .values(
                    current_state=WorkJournalState.IDLE.value,
                    draft_date=None,
                    draft_company=None,
                    draft_duration=None,
                    draft_description=None,
                    draft_is_travel=None,
                    draft_workers=None,
                    message_to_edit=None,
                    additional_data=None
                )
            )
            await self.session.commit()
            return True
        except Exception as e:
            bot_logger.error(f"Error clearing user state for {telegram_user_id}: {e}")
            return False
    
    async def create_work_entry(
        self,
        telegram_user_id: int,
        user_email: str,
        work_date: date,
        company: str,
        work_duration: str,
        work_description: str,
        is_travel: bool,
        worker_names: List[str],  # Теперь список исполнителей
        created_by_user_id: int,
        created_by_name: str
    ) -> WorkJournalEntry:
        """Создать новую запись в журнале работ"""
        import json
        
        entry = WorkJournalEntry(
            telegram_user_id=telegram_user_id,
            user_email=user_email,
            work_date=work_date,
            company=company,
            work_duration=work_duration,
            work_description=work_description,
            is_travel=is_travel,
            worker_names=json.dumps(worker_names, ensure_ascii=False),  # Сохраняем как JSON
            created_by_user_id=created_by_user_id,
            created_by_name=created_by_name,
            n8n_sync_status=N8nSyncStatus.PENDING.value
        )
        
        self.session.add(entry)
        await self.session.commit()
        
        bot_logger.info(f"Created work journal entry {entry.id} for user {telegram_user_id}")
        
        return entry
    
    async def get_work_entries(
        self,
        telegram_user_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        company: Optional[str] = None,
        worker_name: Optional[str] = None,
        is_travel: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[WorkJournalEntry]:
        """Получить записи журнала с фильтрами"""
        
        query = select(WorkJournalEntry).order_by(desc(WorkJournalEntry.work_date))
        
        # Применяем фильтры
        if telegram_user_id:
            query = query.where(WorkJournalEntry.telegram_user_id == telegram_user_id)
        
        if date_from:
            query = query.where(WorkJournalEntry.work_date >= date_from)
        
        if date_to:
            query = query.where(WorkJournalEntry.work_date <= date_to)
        
        if company:
            query = query.where(WorkJournalEntry.company.ilike(f"%{company}%"))
        
        if worker_name:
            # Ищем по любому из исполнителей в JSON массиве
            query = query.where(WorkJournalEntry.worker_names.like(f"%{worker_name}%"))
        
        if is_travel is not None:
            query = query.where(WorkJournalEntry.is_travel == is_travel)
        
        # Применяем пагинацию
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_work_entry_by_id(self, entry_id: int) -> Optional[WorkJournalEntry]:
        """Получить запись по ID"""
        result = await self.session.execute(
            select(WorkJournalEntry).where(WorkJournalEntry.id == entry_id)
        )
        return result.scalar_one_or_none()
    
    async def get_statistics(
        self,
        telegram_user_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """Получить статистику по работам"""
        
        query = select(WorkJournalEntry)
        
        # Применяем фильтры
        if telegram_user_id:
            query = query.where(WorkJournalEntry.telegram_user_id == telegram_user_id)
        
        if date_from:
            query = query.where(WorkJournalEntry.work_date >= date_from)
        
        if date_to:
            query = query.where(WorkJournalEntry.work_date <= date_to)
        
        # Получаем все записи для статистики
        result = await self.session.execute(query)
        entries = result.scalars().all()
        
        if not entries:
            return {
                "total_entries": 0,
                "total_time_hours": 0,
                "travel_count": 0,
                "remote_count": 0,
                "companies": {},
                "workers": {},
                "date_range": None
            }
        
        # Подсчитываем статистику
        total_entries = len(entries)
        travel_count = sum(1 for e in entries if e.is_travel)
        remote_count = total_entries - travel_count
        
        # Группировка по компаниям и исполнителям
        companies = {}
        workers = {}
        
        for entry in entries:
            # Компании
            if entry.company not in companies:
                companies[entry.company] = 0
            companies[entry.company] += 1
            
            # Исполнители (теперь это JSON массив)
            try:
                import json
                worker_list = json.loads(entry.worker_names)
                for worker in worker_list:
                    if worker not in workers:
                        workers[worker] = 0
                    workers[worker] += 1
            except (json.JSONDecodeError, TypeError):
                # Для совместимости со старыми записями
                if entry.worker_names and entry.worker_names not in workers:
                    workers[entry.worker_names] = 0
                    workers[entry.worker_names] += 1
        
        # Сортируем по количеству
        companies = dict(sorted(companies.items(), key=lambda x: x[1], reverse=True))
        workers = dict(sorted(workers.items(), key=lambda x: x[1], reverse=True))
        
        return {
            "total_entries": total_entries,
            "travel_count": travel_count,
            "remote_count": remote_count,
            "travel_percentage": round((travel_count / total_entries) * 100, 1) if total_entries > 0 else 0,
            "remote_percentage": round((remote_count / total_entries) * 100, 1) if total_entries > 0 else 0,
            "companies": companies,
            "workers": workers,
            "date_range": {
                "from": min(e.work_date for e in entries),
                "to": max(e.work_date for e in entries)
            }
        }
    
    async def get_companies(self, active_only: bool = True) -> List[str]:
        """Получить список компаний"""
        query = select(WorkJournalCompany.name).order_by(WorkJournalCompany.display_order)
        
        if active_only:
            query = query.where(WorkJournalCompany.is_active == True)
        
        result = await self.session.execute(query)
        companies = result.scalars().all()
        
        # Если компании не настроены, возвращаем дефолтный список
        if not companies:
            return DEFAULT_COMPANIES.copy()
        
        return list(companies)
    
    async def add_company(self, name: str) -> bool:
        """Добавить новую компанию"""
        try:
            # Проверяем, что компания не существует
            existing = await self.session.execute(
                select(WorkJournalCompany).where(WorkJournalCompany.name == name)
            )
            if existing.scalar_one_or_none():
                return False  # Компания уже существует
            
            # Добавляем новую компанию
            company = WorkJournalCompany(name=name)
            self.session.add(company)
            await self.session.commit()
            
            bot_logger.info(f"Added new company: {name}")
            return True
            
        except Exception as e:
            bot_logger.error(f"Error adding company {name}: {e}")
            return False
    
    async def delete_company(self, name: str) -> Tuple[bool, str]:
        """Удалить компанию из списка"""
        try:
            # Ищем компанию
            result = await self.session.execute(
                select(WorkJournalCompany).where(WorkJournalCompany.name == name)
            )
            company = result.scalar_one_or_none()
            
            if not company:
                return False, "not_found"  # Компания не найдена
            
            # Проверяем, используется ли компания в записях
            entries_count = await self.session.execute(
                select(func.count(WorkJournalEntry.id)).where(WorkJournalEntry.company == name)
            )
            count = entries_count.scalar()
            
            if count > 0:
                bot_logger.warning(f"Cannot delete company {name}: used in {count} entries")
                return False, f"used_in_{count}_entries"  # Компания используется в записях
            
            # Удаляем компанию
            await self.session.delete(company)
            await self.session.commit()
            
            bot_logger.info(f"Deleted company: {name}")
            return True, "success"
            
        except Exception as e:
            bot_logger.error(f"Error deleting company {name}: {e}")
            return False, "error"
    
    async def get_workers(self, active_only: bool = True) -> List[str]:
        """Получить список исполнителей"""
        query = select(WorkJournalWorker.name).order_by(WorkJournalWorker.display_order)
        
        if active_only:
            query = query.where(WorkJournalWorker.is_active == True)
        
        result = await self.session.execute(query)
        workers = result.scalars().all()
        
        # Если исполнители не настроены, возвращаем дефолтный список
        if not workers:
            return DEFAULT_WORKERS.copy()
        
        return list(workers)
    
    async def add_worker(self, name: str) -> bool:
        """Добавить нового исполнителя"""
        try:
            # Проверяем, что исполнитель не существует
            existing = await self.session.execute(
                select(WorkJournalWorker).where(WorkJournalWorker.name == name)
            )
            if existing.scalar_one_or_none():
                return False  # Исполнитель уже существует
            
            # Добавляем нового исполнителя
            worker = WorkJournalWorker(name=name)
            self.session.add(worker)
            await self.session.commit()
            
            bot_logger.info(f"Added new worker: {name}")
            return True
            
        except Exception as e:
            bot_logger.error(f"Error adding worker {name}: {e}")
            return False
    
    async def update_n8n_sync_status(
        self,
        entry_id: int,
        status: N8nSyncStatus,
        error_message: Optional[str] = None,
        increment_attempts: bool = True
    ) -> bool:
        """Обновить статус синхронизации с n8n"""
        try:
            update_data = {
                "n8n_sync_status": status.value,
                "n8n_last_sync_at": datetime.utcnow()
            }
            
            if error_message:
                update_data["n8n_error_message"] = error_message
            
            if increment_attempts:
                # Увеличиваем счетчик попыток
                await self.session.execute(
                    update(WorkJournalEntry)
                    .where(WorkJournalEntry.id == entry_id)
                    .values(n8n_sync_attempts=WorkJournalEntry.n8n_sync_attempts + 1)
                )
            
            await self.session.execute(
                update(WorkJournalEntry)
                .where(WorkJournalEntry.id == entry_id)
                .values(**update_data)
            )
            await self.session.commit()
            
            return True
            
        except Exception as e:
            bot_logger.error(f"Error updating n8n sync status for entry {entry_id}: {e}")
            return False
    
    async def get_pending_sync_entries(self, max_attempts: int = 3) -> List[WorkJournalEntry]:
        """Получить записи, ожидающие синхронизации с n8n"""
        result = await self.session.execute(
            select(WorkJournalEntry)
            .where(
                and_(
                    WorkJournalEntry.n8n_sync_status == N8nSyncStatus.PENDING.value,
                    WorkJournalEntry.n8n_sync_attempts < max_attempts
                )
            )
            .order_by(WorkJournalEntry.created_at)
        )
        return result.scalars().all()


async def init_default_data(session: AsyncSession):
    """Инициализация дефолтных данных (компании и исполнители)"""
    try:
        # Проверяем, есть ли уже компании
        result = await session.execute(select(func.count(WorkJournalCompany.id)))
        companies_count = result.scalar()
        
        if companies_count == 0:
            # Добавляем дефолтные компании
            for i, company_name in enumerate(DEFAULT_COMPANIES):
                company = WorkJournalCompany(
                    name=company_name,
                    display_order=i
                )
                session.add(company)
            
            bot_logger.info(f"Added {len(DEFAULT_COMPANIES)} default companies")
        
        # Проверяем, есть ли уже исполнители
        result = await session.execute(select(func.count(WorkJournalWorker.id)))
        workers_count = result.scalar()
        
        if workers_count == 0:
            # Добавляем дефолтных исполнителей
            for i, worker_name in enumerate(DEFAULT_WORKERS):
                worker = WorkJournalWorker(
                    name=worker_name,
                    display_order=i
                )
                session.add(worker)
            
            bot_logger.info(f"Added {len(DEFAULT_WORKERS)} default workers")
        
        await session.commit()
        
    except Exception as e:
        bot_logger.error(f"Error initializing default data: {e}")
        raise
