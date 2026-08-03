#!/usr/bin/env python
"""
translate_po.py – Automatically translate Django .po files using Google Translate.
Fixed to handle None values and avoid AttributeError.
Usage: python translate_po.py
"""

import os
import polib
from deep_translator import GoogleTranslator
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Language codes
LANG_MAP = {
    'en': 'en',
    'hi': 'hi',
    'mr': 'mr',
}

# Paths to your locale directories (adjust if needed)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALE_PATHS = {
    'en': os.path.join(BASE_DIR, 'locale', 'en', 'LC_MESSAGES', 'django.po'),
    'hi': os.path.join(BASE_DIR, 'locale', 'hi', 'LC_MESSAGES', 'django.po'),
    'mr': os.path.join(BASE_DIR, 'locale', 'mr', 'LC_MESSAGES', 'django.po'),
}


def translate_text(text, target_lang):
    """Translate a single text string to target_lang using deep_translator."""
    if not text or not text.strip():
        return ""
    try:
        translator = GoogleTranslator(source='en', target=target_lang)
        result = translator.translate(text)
        return result if result else ""  # ensure non-None
    except Exception as e:
        logger.warning(f"Translation failed for: '{text}' – {e}")
        return ""  # fallback to empty string


def update_po_file(po_path, source_lang='en', target_lang=None):
    """
    Update a .po file:
      - If target_lang is None, copy msgid to msgstr (for English).
      - Otherwise, translate msgid from source_lang to target_lang.
    """
    if not os.path.exists(po_path):
        logger.error(f"File not found: {po_path}")
        return

    po = polib.pofile(po_path)
    total = len(po)
    logger.info(f"Processing {po_path} ({total} entries)")

    for idx, entry in enumerate(po, 1):
        # Skip if msgid is empty (header or fuzzy)
        if not entry.msgid or entry.msgid.startswith('#'):
            continue

        # Uncomment to skip already translated strings:
        # if entry.msgstr and entry.msgstr.strip() and target_lang:
        #     continue

        if target_lang is None:  # English: copy msgid
            entry.msgstr = entry.msgid
        else:
            # Translate from English to target_lang
            translated = translate_text(entry.msgid, target_lang)
            entry.msgstr = translated  # always a string (maybe empty)

        if idx % 50 == 0:
            logger.info(f"Progress: {idx}/{total}")

    po.save()
    logger.info(f"Saved: {po_path}")


def main():
    # 1. English: copy msgid to msgstr
    update_po_file(LOCALE_PATHS['en'], target_lang=None)

    # 2. Hindi: translate from English to Hindi
    update_po_file(LOCALE_PATHS['hi'], source_lang='en', target_lang='hi')

    # 3. Marathi: translate from English to Marathi
    update_po_file(LOCALE_PATHS['mr'], source_lang='en', target_lang='mr')

    logger.info("All translations updated successfully!")


if __name__ == "__main__":
    main()
