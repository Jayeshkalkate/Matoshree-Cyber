from django.db import OperationalError
from .models import BusinessInfo

def business_info(request):
    try:
        info = BusinessInfo.get_instance()
    except OperationalError:
        info = None
    return {
        'business': info,
        'business_info': info,
    }
    
