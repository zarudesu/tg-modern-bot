#!/usr/bin/env python3
"""
Script to refactor escape_markdown_v2 usage across the codebase

This script will:
1. Remove local definitions of escape_markdown_v2
2. Add imports from app.utils.markdown
3. Update all usages to use centralized function
"""
import os
import re
from pathlib import Path

# Files to update
FILES_TO_UPDATE = [
    "app/modules/daily_tasks/email_handlers.py",
    "app/modules/daily_tasks/handlers.py",
    "app/modules/daily_tasks/callback_handlers.py",
    "app/modules/daily_tasks/navigation_handlers.py",
    "app/modules/support_requests/handlers.py",
    "app/modules/support_requests/handlers_new.py",
    "app/modules/support_requests/admin_handlers.py",
]

FUNCTION_PATTERN = re.compile(
    r"def escape_markdown_v2\(text: str\) -> str:.*?return text",
    re.DOTALL
)

IMPORT_LINE = "from ...utils.markdown import escape_markdown_v2\n"


def remove_function_definition(content: str) -> str:
    """Remove escape_markdown_v2 function definition"""
    # Remove the function and its docstring
    content = FUNCTION_PATTERN.sub("", content)
    return content


def add_import_if_missing(content: str, filepath: str) -> str:
    """Add import statement if not present"""
    if "from ...utils.markdown import" in content:
        print(f"  ✓ Import already present in {filepath}")
        return content

    # Find where to insert import (after other imports)
    lines = content.split('\n')

    # Find last import line
    last_import_idx = 0
    for idx, line in enumerate(lines):
        if line.startswith('from ') or line.startswith('import '):
            last_import_idx = idx

    # Insert after last import
    lines.insert(last_import_idx + 1, IMPORT_LINE.rstrip())

    return '\n'.join(lines)


def main():
    project_root = Path(__file__).parent.parent

    print("🔄 Starting refactor of escape_markdown_v2...")
    print()

    updated_files = 0

    for filepath in FILES_TO_UPDATE:
        full_path = project_root / filepath

        if not full_path.exists():
            print(f"⚠️  File not found: {filepath}")
            continue

        print(f"📝 Processing: {filepath}")

        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Remove function definition
        if "def escape_markdown_v2" in content:
            content = remove_function_definition(content)
            print(f"  ✓ Removed function definition")

        # Add import
        content = add_import_if_missing(content, filepath)

        # Write back if changed
        if content != original_content:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ Updated {filepath}")
            updated_files += 1
        else:
            print(f"  → No changes needed")

        print()

    print(f"✅ Refactor complete! Updated {updated_files} files.")


if __name__ == "__main__":
    main()
