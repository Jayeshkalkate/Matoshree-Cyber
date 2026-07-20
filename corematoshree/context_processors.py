from .models import BusinessInfo

def business_info(request):
    try:
        info = BusinessInfo.objects.first()
    except Exception:
        info = None
    return {
        'business': info,
        'business_info': info,
    }