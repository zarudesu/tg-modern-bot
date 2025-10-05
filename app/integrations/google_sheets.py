"""
Google Sheets интеграция для парсинга данных журнала работ
"""
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import asyncio
from dataclasses import dataclass

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound

from ..config import settings
from ..database.database import get_async_session
from ..database.work_journal_models import WorkJournalEntry, WorkJournalWorker, WorkJournalCompany
from ..services.work_journal_service import WorkJournalService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


@dataclass
class SheetWorkEntry:
    """Модель записи из Google Sheets"""
    timestamp: str
    email: str
    work_date: str
    company: str
    duration: str
    description: str
    is_travel: str
    workers: str
    created_by: str


class GoogleSheetsParser:
    """Парсер Google Sheets для синхронизации данных журнала работ"""
    
    def __init__(self):
        self.service_account_email = "n8n-sheets-integration@hhivp-plane.iam.gserviceaccount.com"
        self.spreadsheet_id = settings.google_sheets_id
        self.credentials = None
        self.client = None
        self.worksheet = None
        
    async def initialize(self) -> bool:
        """Инициализация Google Sheets клиента"""
        try:
            # Получаем credentials из переменных окружения или файла
            if hasattr(settings, 'google_sheets_credentials_json'):
                # Если credentials в JSON формате в переменной окружения
                credentials_info = json.loads(settings.google_sheets_credentials_json)
                self.credentials = Credentials.from_service_account_info(
                    credentials_info,
                    scopes=[
                        'https://www.googleapis.com/auth/spreadsheets.readonly',
                        'https://www.googleapis.com/auth/drive.readonly'
                    ]
                )
            elif hasattr(settings, 'google_sheets_credentials_file'):
                # Если credentials в файле
                self.credentials = Credentials.from_service_account_file(
                    settings.google_sheets_credentials_file,
                    scopes=[
                        'https://www.googleapis.com/auth/spreadsheets.readonly',
                        'https://www.googleapis.com/auth/drive.readonly'
                    ]
                )
            else:
                logger.error("Google Sheets credentials not found in config")
                return False
            
            self.client = gspread.authorize(self.credentials)
            logger.info("Google Sheets client initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")
            return False
    
    async def connect_to_sheet(self) -> bool:
        """Подключение к Google Sheets документу"""
        try:
            if not self.client:
                await self.initialize()
            
            if not self.client:
                return False
            
            # Подключаемся к таблице
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            # Получаем первый лист или лист с нужным названием
            self.worksheet = spreadsheet.get_worksheet(0)  # Первый лист
            
            logger.info(f"Connected to Google Sheet: {spreadsheet.title}")
            return True
            
        except SpreadsheetNotFound:
            logger.error(f"Spreadsheet with ID {self.spreadsheet_id} not found")
            return False
        except APIError as e:
            logger.error(f"Google Sheets API error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheet: {e}")
            return False
    
    async def get_all_entries(self) -> List[Dict[str, Any]]:
        """Получение всех записей из Google Sheets"""
        try:
            if not self.worksheet:
                if not await self.connect_to_sheet():
                    return []
            
            # Получаем все данные
            all_values = self.worksheet.get_all_records()
            logger.info(f"Retrieved {len(all_values)} entries from Google Sheets")
            
            return all_values
            
        except Exception as e:
            logger.error(f"Failed to get entries from Google Sheets: {e}")
            return []
    
    def parse_sheet_entry(self, row_data: Dict[str, Any]) -> Optional[SheetWorkEntry]:
        """Парсинг одной записи из Google Sheets"""
        try:
            # Ожидаемые колонки в таблице (могут отличаться от реальных названий)
            # Адаптируем под реальную структуру таблицы
            
            # Попробуем разные варианты названий колонок
            timestamp_key = self._find_column_key(row_data, ['Timestamp', 'Дата создания', 'Created', 'timestamp'])
            email_key = self._find_column_key(row_data, ['Email Address', 'Email', 'Электронная почта', 'email'])
            date_key = self._find_column_key(row_data, ['work_date', 'Дата работ', 'Date', 'Дата'])
            company_key = self._find_column_key(row_data, ['company', 'Компания', 'Company', 'Клиент'])
            duration_key = self._find_column_key(row_data, ['work_duration', 'Длительность', 'Duration', 'Время'])
            description_key = self._find_column_key(row_data, ['work_description', 'Описание', 'Description', 'Работы'])
            travel_key = self._find_column_key(row_data, ['is_travel', 'Командировка', 'Travel', 'Выезд'])
            workers_key = self._find_column_key(row_data, ['worker_names', 'Исполнители', 'Workers', 'Работники'])
            created_by_key = self._find_column_key(row_data, ['created_by_name', 'Создал', 'Created By', 'Автор'])
            
            if not all([timestamp_key, email_key, date_key, company_key, duration_key, description_key]):
                logger.warning(f"Missing required columns in row: {row_data}")
                return None
            
            return SheetWorkEntry(
                timestamp=str(row_data.get(timestamp_key, '')),
                email=str(row_data.get(email_key, '')),
                work_date=str(row_data.get(date_key, '')),
                company=str(row_data.get(company_key, '')),
                duration=str(row_data.get(duration_key, '')),
                description=str(row_data.get(description_key, '')),
                is_travel=str(row_data.get(travel_key, 'Нет')),
                workers=str(row_data.get(workers_key, '')),
                created_by=str(row_data.get(created_by_key, ''))
            )
            
        except Exception as e:
            logger.error(f"Failed to parse sheet entry: {e}, row_data: {row_data}")
            return None
    
    def _find_column_key(self, row_data: Dict[str, Any], possible_keys: List[str]) -> Optional[str]:
        """Поиск ключа колонки среди возможных вариантов"""
        for key in possible_keys:
            if key in row_data:
                return key
        return None
    
    def parse_date(self, date_str: str) -> Optional[date]:
        """Парсинг даты из различных форматов"""
        if not date_str or date_str.strip() == '':
            return None
        
        date_formats = [
            '%Y-%m-%d',           # 2025-08-04
            '%d.%m.%Y',           # 04.08.2025
            '%d/%m/%Y',           # 04/08/2025
            '%m/%d/%Y',           # 08/04/2025
            '%Y-%m-%d %H:%M:%S',  # 2025-08-04 10:30:00
            '%d.%m.%Y %H:%M:%S',  # 04.08.2025 10:30:00
        ]
        
        for date_format in date_formats:
            try:
                parsed_date = datetime.strptime(date_str.strip(), date_format)
                return parsed_date.date()
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def parse_workers(self, workers_str: str) -> List[str]:
        """Парсинг списка исполнителей"""
        if not workers_str or workers_str.strip() == '':
            return []
        
        # Попробуем разные разделители
        for separator in [',', ';', '\n', '|']:
            if separator in workers_str:
                workers = [w.strip() for w in workers_str.split(separator) if w.strip()]
                if workers:
                    return workers
        
        # Если разделителей нет, возвращаем как один элемент
        return [workers_str.strip()]
    
    async def sync_entries_to_database(self) -> Dict[str, int]:
        """Синхронизация записей из Google Sheets в базу данных"""
        stats = {
            'total_processed': 0,
            'new_entries': 0,
            'skipped_entries': 0,
            'error_entries': 0
        }
        
        try:
            # Получаем данные из Google Sheets
            sheet_data = await self.get_all_entries()
            if not sheet_data:
                logger.warning("No data retrieved from Google Sheets")
                return stats
            
            stats['total_processed'] = len(sheet_data)
            
            async with get_async_session() as session:
                work_service = WorkJournalService(session)
                
                for row_data in sheet_data:
                    try:
                        # Парсим запись
                        sheet_entry = self.parse_sheet_entry(row_data)
                        if not sheet_entry:
                            stats['skipped_entries'] += 1
                            continue
                        
                        # Парсим дату
                        work_date = self.parse_date(sheet_entry.work_date)
                        if not work_date:
                            logger.warning(f"Invalid date in entry: {sheet_entry.work_date}")
                            stats['error_entries'] += 1
                            continue
                        
                        # Парсим исполнителей
                        workers = self.parse_workers(sheet_entry.workers)
                        if not workers:
                            logger.warning(f"No workers found in entry: {sheet_entry.workers}")
                            stats['error_entries'] += 1
                            continue
                        
                        # Проверяем, существует ли уже такая запись
                        existing_entry = await self._find_existing_entry(
                            session, 
                            work_date, 
                            sheet_entry.company, 
                            sheet_entry.description,
                            workers
                        )
                        
                        if existing_entry:
                            logger.debug(f"Entry already exists: {work_date} - {sheet_entry.company}")
                            stats['skipped_entries'] += 1
                            continue
                        
                        # Создаем новую запись
                        await self._create_database_entry(
                            session,
                            sheet_entry,
                            work_date,
                            workers
                        )
                        
                        stats['new_entries'] += 1
                        logger.info(f"Created new entry: {work_date} - {sheet_entry.company}")
                        
                    except Exception as e:
                        logger.error(f"Error processing sheet entry: {e}, data: {row_data}")
                        stats['error_entries'] += 1
                        continue
                
                # Коммитим изменения
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to sync entries to database: {e}")
            stats['error_entries'] = stats['total_processed']
        
        return stats
    
    async def _find_existing_entry(
        self, 
        session: AsyncSession, 
        work_date: date, 
        company: str, 
        description: str,
        workers: List[str]
    ) -> Optional[WorkJournalEntry]:
        """Поиск существующей записи в базе данных"""
        try:
            # Ищем по дате, компании и описанию
            stmt = select(WorkJournalEntry).where(
                WorkJournalEntry.work_date == work_date,
                WorkJournalEntry.company == company,
                WorkJournalEntry.work_description == description
            )
            
            result = await session.execute(stmt)
            existing_entry = result.scalar_one_or_none()
            
            return existing_entry
            
        except Exception as e:
            logger.error(f"Error finding existing entry: {e}")
            return None
    
    async def _create_database_entry(
        self,
        session: AsyncSession,
        sheet_entry: SheetWorkEntry,
        work_date: date,
        workers: List[str]
    ):
        """Создание записи в базе данных"""
        try:
            # Определяем telegram_user_id и created_by_user_id
            # Поскольку данные из Google Sheets, используем системного пользователя
            system_user_id = settings.admin_user_id_list[0] if settings.admin_user_id_list else 0
            
            # Определяем статус командировки
            is_travel = sheet_entry.is_travel.lower() in ['да', 'yes', 'true', '1', 'командировка']
            
            # Создаем запись
            new_entry = WorkJournalEntry(
                telegram_user_id=system_user_id,
                user_email=sheet_entry.email,
                work_date=work_date,
                company=sheet_entry.company,
                work_duration=sheet_entry.duration,
                work_description=sheet_entry.description,
                is_travel=is_travel,
                worker_names=json.dumps(workers, ensure_ascii=False),
                created_by_user_id=system_user_id,
                created_by_name=sheet_entry.created_by or "Google Sheets Import",
                n8n_sync_status='imported_from_sheets'
            )
            
            session.add(new_entry)
            
        except Exception as e:
            logger.error(f"Error creating database entry: {e}")
            raise


class GoogleSheetsService:
    """Сервис для работы с Google Sheets"""
    
    def __init__(self):
        self.parser = GoogleSheetsParser()
    
    async def sync_from_sheets(self) -> Dict[str, int]:
        """Синхронизация данных из Google Sheets в базу данных"""
        logger.info("Starting Google Sheets synchronization")
        
        try:
            # Инициализируем парсер
            if not await self.parser.initialize():
                logger.error("Failed to initialize Google Sheets parser")
                return {'total_processed': 0, 'new_entries': 0, 'skipped_entries': 0, 'error_entries': 0}
            
            # Синхронизируем данные
            stats = await self.parser.sync_entries_to_database()
            
            logger.info(f"Google Sheets sync completed. Stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Google Sheets sync failed: {e}")
            return {'total_processed': 0, 'new_entries': 0, 'skipped_entries': 0, 'error_entries': 1}
    
    async def get_sheet_preview(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение превью данных из Google Sheets"""
        try:
            if not await self.parser.initialize():
                return []
            
            sheet_data = await self.parser.get_all_entries()
            return sheet_data[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get sheet preview: {e}")
            return []


# Глобальный экземпляр сервиса
sheets_service = GoogleSheetsService()
