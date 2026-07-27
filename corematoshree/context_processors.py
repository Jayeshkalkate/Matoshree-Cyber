from .models import BusinessInfo
from .utils import get_payment_settings

def business_info(request):
    try:
        info = BusinessInfo.objects.first()
    except Exception:
        info = None
    return {'business': info, 'business_info': info}

def payment_settings(request):
    return {'payment_settings': get_payment_settings()}