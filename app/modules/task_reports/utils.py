"""
Task Reports Utility Functions

Helper functions and mappings for task reports module
"""

from ...utils.logger import bot_logger


# Company name mapping: Plane → наши названия
COMPANY_MAPPING = {
    "HarzLabs": "Харц Лабз",
    "3D.RU": "3Д.РУ",
    "Garden of Health": "Сад Здоровья",
    "Delta": "Дельта",
    "Moiseev": "Моисеев",
    "Stifter": "Стифтер",
    "Vekha": "Веха",
    "Sosnovy Bor": "Сосновый бор",
    "Bibirevo": "Бибирево",
    "Romashka": "Ромашка",
    "Vyoshki 95": "Вёшки 95",
    "Vondiga Park": "Вондига Парк",
    "Iva": "Ива",
    "CifraCifra": "ЦифраЦифра"
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
