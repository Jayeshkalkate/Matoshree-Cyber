from django.core.management.base import BaseCommand
from corematoshree.models import PaymentSettings
from corematoshree.utils import get_payment_settings
import razorpay
import os

class Command(BaseCommand):
    help = 'Test Razorpay connectivity with current credentials'

    def handle(self, *args, **options):
        # 1. Try environment variables
        key_id = os.getenv('RAZORPAY_KEY_ID') or os.getenv('RAZORPAY_TEST_KEY_ID')
        key_secret = os.getenv('RAZORPAY_KEY_SECRET') or os.getenv('RAZORPAY_TEST_KEY_SECRET')
        source = 'env'

        # 2. If missing, try database
        if not key_id or not key_secret:
            payment_settings = get_payment_settings()
            if payment_settings:
                if payment_settings.test_mode:
                    key_id = payment_settings.razorpay_test_key
                    key_secret = payment_settings.razorpay_test_secret
                else:
                    key_id = payment_settings.razorpay_key_id
                    key_secret = payment_settings.razorpay_key_secret
                source = 'database'

        # 3. Still missing? raise error
        if not key_id or not key_secret:
            self.stdout.write(self.style.ERROR("❌ Razorpay credentials not found in environment or database."))
            self.stdout.write("   Please set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET, or update PaymentSettings.")
            return

        masked_key = key_id[:4] + "****" + key_id[-4:] if len(key_id) > 8 else "****"
        self.stdout.write(f"🔑 Using key: {masked_key} (source: {source})")

        try:
            client = razorpay.Client(auth=(key_id, key_secret))
            # Test by fetching orders (without limit parameter to avoid errors)
            orders = client.order.all()
            self.stdout.write(self.style.SUCCESS("✅ Razorpay connection successful."))
            # Print first few orders if any
            items = orders.get('items', [])
            self.stdout.write(f"   Orders fetched: {len(items)}")
            if items:
                first_order = items[0]
                self.stdout.write(f"   Latest order ID: {first_order.get('id')}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Razorpay error: {e}"))