"""
Клавиатуры для модуля task_reports

Удобный UI с кнопками как в work_journal
"""
from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# Константы (русский формат как в work_journal)
DEFAULT_DURATIONS = [
    "5 мин",
    "10 мин",
    "15 мин",
    "30 мин",
    "45 мин",
    "1 час",
    "1.5 часа",
    "2 часа"
]
EMOJI = {
    'duration': '⏱️',
    'travel': '🚗',
    'remote': '💻',
    'company': '🏢',
    'worker': '👤',
    'add': '➕',
    'back': '◀️',
    'cancel': '❌',
    'check': '✅',
    'edit': '✏️',
    'group': '💬'
}


def create_duration_keyboard(task_report_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора длительности работ"""
    builder = InlineKeyboardBuilder()

    # Кнопки с предустановленными длительностями (по 2 в ряд)
    for i in range(0, len(DEFAULT_DURATIONS), 2):
        row_buttons = []
        for j in range(i, min(i + 2, len(DEFAULT_DURATIONS))):
            duration = DEFAULT_DURATIONS[j]
            row_buttons.append(
                InlineKeyboardButton(
                    text=f"{EMOJI['duration']} {duration}",
                    callback_data=f"tr_duration:{task_report_id}:{duration}"
                )
            )
        builder.row(*row_buttons)

    # Кнопка "Другое время"
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['add']} Другое время",
            callback_data=f"tr_custom_duration:{task_report_id}"
        )
    )

    # Навигация
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад к тексту",
            callback_data=f"fill_report:{task_report_id}"
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cancel']} Отменить",
            callback_data=f"cancel_report:{task_report_id}"
        )
    )

    return builder.as_markup()


def create_work_type_keyboard(task_report_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора типа работы (Выезд/Удалённо)"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['travel']} Да, был выезд",
            callback_data=f"tr_travel:{task_report_id}:yes"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['remote']} Нет, удаленно",
            callback_data=f"tr_travel:{task_report_id}:no"
        )
    )

    # Навигация
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад",
            callback_data=f"tr_back_to_duration:{task_report_id}"
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cancel']} Отменить",
            callback_data=f"cancel_report:{task_report_id}"
        )
    )

    return builder.as_markup()


def create_company_keyboard(companies: List[str], task_report_id: int, plane_company: str = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора компании"""
    builder = InlineKeyboardBuilder()

    # Если есть компания из Plane - показываем её первой
    if plane_company:
        builder.row(
            InlineKeyboardButton(
                text=f"{EMOJI['company']} {plane_company} (из Plane)",
                callback_data=f"tr_company:{task_report_id}:{plane_company}"
            )
        )

    # Кнопки с компаниями (по 2 в ряд)
    for i in range(0, len(companies), 2):
        row_buttons = []
        for j in range(i, min(i + 2, len(companies))):
            company = companies[j]
            # Пропускаем если это та же компания что из Plane
            if company == plane_company:
                continue
            row_buttons.append(
                InlineKeyboardButton(
                    text=company,
                    callback_data=f"tr_company:{task_report_id}:{company}"
                )
            )
        if row_buttons:
            builder.row(*row_buttons)

    # Кнопка "Другая компания"
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['add']} Другая компания",
            callback_data=f"tr_custom_company:{task_report_id}"
        )
    )

    # Навигация
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад",
            callback_data=f"tr_back_to_work_type:{task_report_id}"
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cancel']} Отменить",
            callback_data=f"cancel_report:{task_report_id}"
        )
    )

    return builder.as_markup()


def create_workers_keyboard(
    workers: List[str],
    task_report_id: int,
    selected_workers: List[str] = None,
    plane_assignees: List[str] = None
) -> InlineKeyboardMarkup:
    """Клавиатура выбора исполнителей (множественный выбор)"""
    builder = InlineKeyboardBuilder()

    if selected_workers is None:
        selected_workers = []

    # Если есть исполнители из Plane - показываем кнопку "Все из Plane"
    if plane_assignees:
        all_selected = all(assignee in selected_workers for assignee in plane_assignees)
        prefix = f"{EMOJI['check']} " if all_selected else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{prefix}Все исполнители из Plane ({len(plane_assignees)})",
                callback_data=f"tr_workers_all_plane:{task_report_id}"
            )
        )

    # Кнопки с исполнителями (с индикацией выбора)
    for worker in workers:
        is_selected = worker in selected_workers
        is_from_plane = plane_assignees and worker in plane_assignees

        # Формируем текст кнопки
        prefix = f"{EMOJI['check']} " if is_selected else ""
        suffix = " (из Plane)" if is_from_plane else ""

        builder.row(
            InlineKeyboardButton(
                text=f"{prefix}{worker}{suffix}",
                callback_data=f"tr_toggle_worker:{task_report_id}:{worker}"
            )
        )

    # Кнопка "Добавить исполнителя"
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['add']} Добавить исполнителя",
            callback_data=f"tr_add_worker:{task_report_id}"
        )
    )

    # Кнопка "Подтвердить выбор" (показывается только если что-то выбрано)
    if selected_workers:
        builder.row(
            InlineKeyboardButton(
                text=f"{EMOJI['check']} Подтвердить выбор ({len(selected_workers)})",
                callback_data=f"tr_confirm_workers:{task_report_id}"
            )
        )

    # Навигация
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад",
            callback_data=f"tr_back_to_company:{task_report_id}"
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cancel']} Отменить",
            callback_data=f"cancel_report:{task_report_id}"
        )
    )

    return builder.as_markup()


def create_final_review_keyboard(task_report_id: int, has_client: bool) -> InlineKeyboardMarkup:
    """Клавиатура финального просмотра перед отправкой"""
    builder = InlineKeyboardBuilder()

    # Кнопка редактирования
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['edit']} Редактировать",
            callback_data=f"edit_report:{task_report_id}"
        )
    )

    # Кнопка отправки (если есть клиент)
    if has_client:
        builder.row(
            InlineKeyboardButton(
                text=f"{EMOJI['check']} Отправить клиенту",
                callback_data=f"approve_send:{task_report_id}"
            )
        )

    # Кнопка "Отправить в группу" (ВСЕГДА доступна)
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['group']} Отправить в группу",
            callback_data=f"send_to_group:{task_report_id}"
        )
    )

    # Кнопка "Продолжить без отправки" (вместо "Закрыть без отчёта")
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['check']} Продолжить без отправки",
            callback_data=f"approve_only:{task_report_id}"
        )
    )

    # Кнопка "Закрыть без отчёта"
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['cancel']} Закрыть без отчёта",
            callback_data=f"close_no_report:{task_report_id}"
        )
    )

    return builder.as_markup()
