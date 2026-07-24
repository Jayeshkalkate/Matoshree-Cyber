# management/commands/send_payment_reminders.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Send payment reminders to pending applications'
    
    def handle(self, *args, **options):
        pending_apps = Application.objects.filter(
            payment_status='pending',
            created_at__gte=timezone.now() - timedelta(days=2)
        )
        
        for app in pending_apps:
            # Send reminder email
            send_payment_reminder(app)
            self.stdout.write(f"Reminder sent to {app.email}")