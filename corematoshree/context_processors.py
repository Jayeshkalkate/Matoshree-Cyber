from .models import BusinessInfo
from .models import PaymentSettings

def business_info(request):
    try:
        info = BusinessInfo.objects.first()
    except Exception:
        info = None
    return {
        'business': info,
        'business_info': info,
    }

def payment_settings(request):
    return {
        'payment_settings': PaymentSettings.objects.filter(is_active=True).first()
    }
    
