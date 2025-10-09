"""
Markdown utilities for Telegram bot messages

CANONICAL implementation of MarkdownV2 escaping
All modules MUST import from this file
"""


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2 format

    Args:
        text: Raw text to escape

    Returns:
        Escaped text safe for MarkdownV2

    Usage:
        from app.utils.markdown import escape_markdown_v2

        message = escape_markdown_v2("Hello [World]!")
        await bot.send_message(chat_id, message, parse_mode="MarkdownV2")
    """
    if not text:
        return ""

    # Characters that need escaping in MarkdownV2
    chars_to_escape = [
        '_', '*', '[', ']', '(', ')', '~', '`',
        '>', '#', '+', '-', '=', '|', '{', '}',
        '.', '!', '@'
    ]

    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')

    return text


# Alias for backward compatibility
escape_markdown = escape_markdown_v2
