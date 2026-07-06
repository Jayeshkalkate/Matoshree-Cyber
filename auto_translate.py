import polib
from deep_translator import GoogleTranslator
        
LANGUAGES = {
    "mr": "marathi",
    "hi": "hindi",
}

for code, language in LANGUAGES.items():
    po_path = f"locale/{code}/LC_MESSAGES/django.po"

    po = polib.pofile(po_path)
    translator = GoogleTranslator(source="en", target=language)

    for entry in po:
        if entry.msgid and not entry.msgstr:
            try:
                translated = translator.translate(entry.msgid)
                
                if translated is None:
                    translated = entry.msgid  # Keep original if translation fails
                    
                entry.msgstr = translated
                print(f"[{code}] {entry.msgid} -> {translated}")
                    
            except Exception as e:
                print(f"Error translating '{entry.msgid}': {e}")
                entry.msgstr = entry.msgid
    po.save()