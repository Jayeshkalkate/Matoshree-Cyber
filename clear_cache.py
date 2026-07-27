# ================================================================
# clear_cache.py – Clear all Django cache
# ================================================================

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Matoshree.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import django
django.setup()

from django.core.cache import cache

print("🧹 Clearing all cache...")
cache.clear()
print("✅ Cache cleared successfully!")