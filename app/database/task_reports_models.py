"""
Task Reports Models - Отчёты о выполненных задачах для клиентов

Когда задача в Plane закрывается (переводится в Done), создаётся TaskReport.
Админ должен заполнить отчёт о выполненной работе, который отправится клиенту.
"""

from sqlalchemy import Column, Integer, String, Text, BigInteger, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .models import Base


class TaskReport(Base):
    """
    Отчёты о выполненных задачах

    Создаётся автоматически когда задача в Plane переводится в Done.
    Админ заполняет отчёт → отправляется клиенту в чат.
    """
    __tablename__ = "task_reports"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # ═══════════════════════════════════════════════════════════
    # СВЯЗЬ С SUPPORT REQUEST
    # ═══════════════════════════════════════════════════════════
    support_request_id = Column(
        Integer,
        ForeignKey("support_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Связь с заявкой поддержки (если есть)"
    )

    # Relationship
    support_request = relationship("SupportRequest", backref="task_reports")

    # ═══════════════════════════════════════════════════════════
    # PLANE TASK INFORMATION
    # ═══════════════════════════════════════════════════════════
    plane_issue_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="UUID задачи в Plane"
    )

    plane_sequence_id = Column(
        Integer,
        nullable=True,
        comment="Номер задачи (HHIVP-123)"
    )

    plane_project_id = Column(
        String(255),
        nullable=True,
        comment="UUID проекта в Plane"
    )

    task_title = Column(
        String(500),
        nullable=True,
        comment="Название задачи"
    )

    task_description = Column(
        Text,
        nullable=True,
        comment="Описание задачи (для контекста)"
    )

    # ═══════════════════════════════════════════════════════════
    # КТО ЗАКРЫЛ ЗАДАЧУ (actor из Plane webhook)
    # ═══════════════════════════════════════════════════════════
    closed_by_plane_name = Column(
        String(255),
        nullable=True,
        comment="Имя из Plane (display_name / first_name)"
    )

    closed_by_telegram_username = Column(
        String(255),
        nullable=True,
        comment="Telegram username (@zardes) после маппинга"
    )

    closed_by_telegram_id = Column(
        BigInteger,
        nullable=True,
        index=True,
        comment="Telegram User ID админа (приоритет для напоминаний)"
    )

    closed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда задача была закрыта в Plane"
    )

    # ═══════════════════════════════════════════════════════════
    # ОТЧЁТ (основной контент)
    # ═══════════════════════════════════════════════════════════
    report_text = Column(
        Text,
        nullable=True,
        comment="Текст отчёта для клиента (что было сделано)"
    )

    report_submitted_by = Column(
        BigInteger,
        nullable=True,
        comment="Telegram user_id админа, который заполнил отчёт"
    )

    report_submitted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда отчёт был заполнен"
    )

    # ═══════════════════════════════════════════════════════════
    # ИНТЕГРАЦИЯ С WORK JOURNAL (если есть)
    # ═══════════════════════════════════════════════════════════
    work_journal_entry_id = Column(
        Integer,
        ForeignKey("work_journal_entries.id", ondelete="SET NULL"),
        nullable=True,
        comment="Связь с записью work journal (опционально)"
    )

    auto_filled_from_journal = Column(
        Boolean,
        default=False,
        comment="Был ли отчёт автоматически заполнен из work journal"
    )

    # ═══════════════════════════════════════════════════════════
    # МЕТАДАННЫЕ РАБОТЫ (как в work journal)
    # ═══════════════════════════════════════════════════════════
    work_duration = Column(
        String(50),
        nullable=True,
        comment="Длительность работы (напр. '2h', '4h')"
    )

    is_travel = Column(
        Boolean,
        nullable=True,
        comment="Выезд (True) или удалённо (False)"
    )

    company = Column(
        String(255),
        nullable=True,
        comment="Компания/проект для которого выполнялась работа"
    )

    workers = Column(
        Text,
        nullable=True,
        comment="JSON массив исполнителей ['Имя1', 'Имя2']"
    )

    # ═══════════════════════════════════════════════════════════
    # СТАТУСЫ ОТЧЁТА
    # ═══════════════════════════════════════════════════════════
    status = Column(
        String(50),
        default='pending',
        nullable=False,
        index=True,
        comment="pending → draft → approved → sent_to_client"
    )
    # pending - ждём отчёт от админа
    # draft - админ написал, проверяет
    # approved - админ одобрил
    # sent_to_client - отправлено клиенту
    # cancelled - отменено

    # ═══════════════════════════════════════════════════════════
    # СИСТЕМА НАПОМИНАНИЙ
    # ═══════════════════════════════════════════════════════════
    reminder_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Сколько напоминаний отправлено"
    )

    last_reminder_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда последнее напоминание отправлено"
    )

    reminder_level = Column(
        Integer,
        default=0,
        comment="Уровень агрессивности напоминаний (0-3)"
    )

    # ═══════════════════════════════════════════════════════════
    # КЛИЕНТ (кому отправить отчёт)
    # ═══════════════════════════════════════════════════════════
    client_chat_id = Column(
        BigInteger,
        nullable=True,
        index=True,
        comment="Chat ID где создавалась заявка"
    )

    client_user_id = Column(
        BigInteger,
        nullable=True,
        comment="User ID клиента (опционально)"
    )

    client_message_id = Column(
        BigInteger,
        nullable=True,
        comment="ID исходного сообщения заявки (для reply)"
    )

    client_notified_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда клиенту отправлен отчёт"
    )

    # ═══════════════════════════════════════════════════════════
    # МЕТАДАННЫЕ
    # ═══════════════════════════════════════════════════════════
    webhook_payload = Column(
        Text,
        nullable=True,
        comment="JSON payload от n8n webhook (для дебага)"
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="Сообщение об ошибке если что-то пошло не так"
    )

    notes = Column(
        Text,
        nullable=True,
        comment="Внутренние заметки (не видны клиенту)"
    )

    # ═══════════════════════════════════════════════════════════
    # ВРЕМЕННЫЕ МЕТКИ
    # ═══════════════════════════════════════════════════════════
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Когда создан TaskReport"
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Последнее обновление"
    )

    # ═══════════════════════════════════════════════════════════
    # ИНДЕКСЫ
    # ═══════════════════════════════════════════════════════════
    __table_args__ = (
        Index('idx_task_reports_status', 'status'),
        Index('idx_task_reports_pending', 'status', 'closed_by_telegram_id'),
        Index('idx_task_reports_reminders', 'status', 'last_reminder_at'),
        Index('idx_task_reports_client', 'client_chat_id', 'created_at'),
    )

    def __repr__(self):
        return f"<TaskReport(id={self.id}, plane_seq={self.plane_sequence_id}, status={self.status})>"

    @property
    def is_pending(self) -> bool:
        """Ждёт заполнения отчёта"""
        return self.status == 'pending'

    @property
    def is_overdue(self) -> bool:
        """Отчёт просрочен (больше 1 часа без ответа)"""
        if not self.closed_at:
            return False
        return (datetime.now(timezone.utc) - self.closed_at).total_seconds() > 3600

    @property
    def hours_since_closed(self) -> float:
        """Сколько часов прошло с закрытия задачи"""
        if not self.closed_at:
            return 0
        return (datetime.now(timezone.utc) - self.closed_at).total_seconds() / 3600
