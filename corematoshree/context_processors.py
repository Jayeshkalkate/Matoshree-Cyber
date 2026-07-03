from django.db import OperationalError
from .models import BusinessInfo

def business_info(request):
    try:
        info = BusinessInfo.get_instance()   # uses singleton logic
    except OperationalError:
        info = None
    return {'business_info': info}