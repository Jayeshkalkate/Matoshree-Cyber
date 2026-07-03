from django.db import OperationalError
from .models import BusinessInfo

def business_info(request):
    try:
        info = BusinessInfo.objects.first()
        if info is None:
            # Create a default record if the table exists but is empty
            info, _ = BusinessInfo.objects.get_or_create(
                id=1,
                defaults={
                    'business_name': 'Matoshree Cyber Café',
                    'welcome_message': 'Welcome to our cyber services!',
                    'phone': '+919876543210',
                    'whatsapp': '+919876543210',
                    'email': 'info@matoshree.com',
                    'address': 'Shop No. 12, Main Road, Pune',
                    'business_hours': 'Mon–Sat: 9 AM – 8 PM\nSun: 10 AM – 2 PM',
                    'google_map': '',
                }
            )
    except OperationalError:
        # Table doesn't exist yet – fallback to None (will be handled in templates)
        info = None
    return {'business_info': info}