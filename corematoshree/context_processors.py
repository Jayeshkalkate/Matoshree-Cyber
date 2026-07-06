from django.db import OperationalError
from .models import BusinessInfo

def business_info(request):
    try:
        info = BusinessInfo.get_instance()   # uses singleton logic
    except OperationalError:
        info = None
    # Return both 'business' and 'business_info'
    return {
        'business': info,
        'business_info': info,
    }
    
