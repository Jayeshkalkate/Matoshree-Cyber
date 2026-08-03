#!/usr/bin/env python3
"""
Remove all internationalization (i18n) from a Django project.
Run this script from the project root (where manage.py lives).
"""

import os
import re
import shutil


def process_file(filepath, pattern, replacement, flags=0):
    """Replace a regex pattern in a file and write back if changed."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Skip binary files (should not happen with .html/.py)
        return

    new_content = re.sub(pattern, replacement, content, flags=flags)
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated: {filepath}")


def main():
    # Walk through the current directory
    for root, dirs, files in os.walk('.'):
        # Skip common directories that shouldn't be touched
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'locale', 'env', 'venv', 'node_modules')]

        for file in files:
            filepath = os.path.join(root, file)

            # ------------------------------------------------------------
            # HTML templates
            # ------------------------------------------------------------
            if file.endswith('.html'):
                # 1. Remove {% load i18n %}
                process_file(filepath, r'{%\s*load\s+i18n\s*%}', '')

                # 2. Replace {% trans "..." %} with the inner text
                process_file(filepath, r'{%\s*trans\s+"([^"]*)"\s*%}', r'\1')
                process_file(filepath, r"{%\s*trans\s+'([^']*)'\s*%}", r'\1')

                # 3. Replace {% blocktrans %}...{% endblocktrans %} (multiline)
                process_file(
                    filepath,
                    r'{%\s*blocktrans\s*%}(.*?){%\s*endblocktrans\s*%}',
                    r'\1',
                    flags=re.DOTALL
                )

                # 4. Remove any remaining {% trans ... %} (safety)
                process_file(filepath, r'{%\s*trans\s+[^%]*%}', '')

            # ------------------------------------------------------------
            # Python files
            # ------------------------------------------------------------
            elif file.endswith('.py'):
                # 1. Remove import lines
                process_file(filepath, r'from django\.utils\.translation import.*\n?', '')
                process_file(filepath, r'\n?', '')

                # 2. Replace ... with the inner text
                process_file(filepath, r'_\(["\']([^"\']*)["\']\)', r'\1')

    # ------------------------------------------------------------
    # Special handling for settings.py and urls.py
    # ------------------------------------------------------------
    settings_path = 'settings.py'
    if os.path.exists(settings_path):
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove LANGUAGES and LOCALE_PATHS assignments (multiline)
        content = re.sub(r'^LANGUAGES\s*=\s*\[.*?\]\s*\n?', '', content, flags=re.MULTILINE | re.DOTALL)
        content = re.sub(r'^LOCALE_PATHS\s*=\s*\[.*?\]\s*\n?', '', content, flags=re.MULTILINE | re.DOTALL)

        # Remove LocaleMiddleware and i18n context processor lines
        content = re.sub(r"^.*'django\.middleware\.locale\.LocaleMiddleware'.*\n?", '', content, flags=re.MULTILINE)
        content = re.sub(r"^.*'django\.template\.context_processors\.i18n'.*\n?", '', content, flags=re.MULTILINE)

        with open(settings_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {settings_path}")

    urls_path = 'urls.py'
    if os.path.exists(urls_path):
        with open(urls_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Remove the i18n URL pattern
        content = re.sub(r"^.*path\('i18n/', include\('django\.conf\.urls\.i18n'\).*\n?", '', content, flags=re.MULTILINE)
        with open(urls_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {urls_path}")

    # ------------------------------------------------------------
    # Delete the locale folder (if it exists)
    # ------------------------------------------------------------
    locale_path = 'locale'
    if os.path.exists(locale_path):
        shutil.rmtree(locale_path)
        print(f"Deleted: {locale_path}")

    print("\n✅ i18n removal complete! Check your site now.")


if __name__ == '__main__':
    main()
