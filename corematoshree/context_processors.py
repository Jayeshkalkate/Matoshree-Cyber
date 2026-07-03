from .models import BusinessInfo

def business_info(request):
    """
    Context processor that makes the BusinessInfo instance available
    to all templates as 'business_info'.
    """
    return {
        'business_info': BusinessInfo.objects.first()
    }