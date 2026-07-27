# corematoshree/utils.py
from django.core.cache import cache
from .models import BusinessInfo, PaymentSettings

def get_business():
    cache_key = 'business_info'
    business = cache.get(cache_key)
    if business is None:
        try:
            business = BusinessInfo.objects.first()
        except Exception:
            business = None
        cache.set(cache_key, business, 60 * 60)
    return business

def get_payment_settings():
    cache_key = 'payment_settings'
    settings_obj = cache.get(cache_key)
    if settings_obj is None:
        settings_obj = PaymentSettings.objects.filter(is_active=True).first()
        if not settings_obj:
            settings_obj = PaymentSettings.objects.create(is_active=False)
        cache.set(cache_key, settings_obj, 60 * 60)
    return settings_obj

def is_admin(user):
    return user.is_authenticated and user.role in ('admin', 'superadmin')

def is_superadmin(user):
    return user.is_authenticated and user.role == 'superadmin'