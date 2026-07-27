# python manage.py setup_payment
from django.core.management.base import BaseCommand
from corematoshree.models import PaymentSettings
import os

class Command(BaseCommand):
    def handle(self, *args, **options):
        settings, created = PaymentSettings.objects.get_or_create(
            is_active=True,
            defaults={
                'razorpay_enabled': True,
                'test_mode': True,
                'razorpay_test_key': os.getenv('RAZORPAY_TEST_KEY_ID', ''),
                'razorpay_test_secret': os.getenv('RAZORPAY_TEST_KEY_SECRET', ''),
                'upi_enabled': True,
            }
        )
        if not created:
            # Update with env values if empty
            if not settings.razorpay_test_key:
                settings.razorpay_test_key = os.getenv('RAZORPAY_TEST_KEY_ID', '')
            if not settings.razorpay_test_secret:
                settings.razorpay_test_secret = os.getenv('RAZORPAY_TEST_KEY_SECRET', '')
            settings.save()
        self.stdout.write("Payment settings updated.")