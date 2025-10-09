"""
Task Reports Utility Functions

Helper functions and mappings for task reports module
"""

from ...utils.logger import bot_logger


# ═══════════════════════════════════════════════════════════
# USER MAPPINGS: TELEGRAM USERNAME → DISPLAY NAME & HANDLE
# ═══════════════════════════════════════════════════════════

# For preview display: telegram_username → short display name
TELEGRAM_TO_DISPLAY_NAME = {
    "zardes": "Костя",
    "dima_gusev": "Дима",
    "timofey_batyrev": "Тимофей",
}

# For group messages: telegram_username → @handle
TELEGRAM_TO_HANDLE = {
    "zardes": "@zardes",
    "dima_gusev": "@gendir_hhivp",
    "timofey_batyrev": "@spiritphoto",
}


def map_workers_to_display_names(workers_list: list) -> str:
    """
    Map telegram usernames to display names for preview

    Args:
        workers_list: List of telegram usernames (e.g., ["zardes", "dima_gusev"])

    Returns:
        str: Comma-separated display names (e.g., "Костя, Дима")
    """
    display_names = []
    for worker in workers_list:
        display_name = TELEGRAM_TO_DISPLAY_NAME.get(worker, worker)
        display_names.append(display_name)
    return ", ".join(display_names)


def map_workers_to_display_names_list(workers_list: list) -> list:
    """
    Map telegram usernames to display names (returns list for work_journal)

    Args:
        workers_list: List of telegram usernames (e.g., ["zardes", "dima_gusev"])

    Returns:
        list: List of display names (e.g., ["Костя", "Дима"])
    """
    display_names = []
    for worker in workers_list:
        display_name = TELEGRAM_TO_DISPLAY_NAME.get(worker, worker)
        display_names.append(display_name)
    return display_names


def map_worker_to_handle(telegram_username: str) -> str:
    """
    Map telegram username to @handle for group messages

    Args:
        telegram_username: Telegram username (e.g., "zardes")

    Returns:
        str: @handle (e.g., "@zardes")
    """
    return TELEGRAM_TO_HANDLE.get(telegram_username, f"@{telegram_username}")


# ═══════════════════════════════════════════════════════════
# COMPANY MAPPING
# ═══════════════════════════════════════════════════════════

# Company name mapping: Plane → наши названия
COMPANY_MAPPING = {
    "HarzLabs": "Харц Лабз",
    "3D.RU": "3Д.РУ",
    "Garden of Health": "Сад Здоровья",
    "Сад Здоровья": "Сад Здоровья",
    "Delta": "Дельта",
    "АО Дельта": "Дельта",
    "Moiseev": "Моисеев",
    "ИП Моисеев": "Моисеев",
    "Stifter": "Стифтер",
    "Стифтер Хаус": "Стифтер",
    "Vekha": "Веха",
    "УК Веха": "Веха",
    "Sosnovy Bor": "Сосновый бор",
    "Сосновый Бор": "Сосновый бор",
    "Bibirevo": "Бибирево",
    "Romashka": "Ромашка",
    "Ромашка": "Ромашка",
    "Vyoshki 95": "Вёшки 95",
    "Vondiga Park": "Вондига Парк",
    "Вондига Парк": "Вондига Парк",
    "Iva": "Ива",
    "Ива": "Ива",
    "CifraCifra": "ЦифраЦифра",
    "ЦифраЦифра": "ЦифраЦифра",

    # Дополнительные проекты
    "hhivp and all": "hhivp and all",
    "Бастион (Алтушка 41 каб 101)": "Бастион",
    "Банком": "Банком",
    "reg.ru": "reg.ru",
    "web-разработка": "web-разработка",
}


def map_company_name(plane_name: str) -> str:
    """
    Map Plane company name to our internal Russian name

    Args:
        plane_name: Company name from Plane project

    Returns:
        str: Mapped Russian company name or original if not found
    """
    mapped = COMPANY_MAPPING.get(plane_name, plane_name)
    if mapped != plane_name:
        bot_logger.info(f"🔄 Mapped company: '{plane_name}' → '{mapped}'")
    return mapped


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for MarkdownV2

    Args:
        text: Text to escape

    Returns:
        str: Escaped text safe for MarkdownV2
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def parse_report_id_safely(callback_data: str, index: int = 1) -> int:
    """
    Safely parse report_id from callback_data

    Args:
        callback_data: The callback data string (e.g., "tr_duration:123:2h")
        index: Index of report_id in split array (default 1)

    Returns:
        int: The report_id

    Raises:
        ValueError: If report_id is invalid or "None"
    """
    try:
        parts = callback_data.split(":")
        report_id_str = parts[index]

        if report_id_str == "None" or not report_id_str or report_id_str == "null":
            raise ValueError(f"Invalid report_id: '{report_id_str}'")

        return int(report_id_str)

    except (IndexError, ValueError) as e:
        bot_logger.error(f"Error parsing report_id from callback_data '{callback_data}': {e}")
        raise ValueError(f"Invalid callback data format")
