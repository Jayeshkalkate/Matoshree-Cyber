from pathlib import Path
from django.core.management import BaseCommand, call_command
from django.conf import settings
from django.utils import timezone


class Command(BaseCommand):
    help = 'Export application data to a timestamped JSON backup file.'

    def handle(self, *args, **options):
        backup_dir = Path(settings.BASE_DIR) / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        filename = backup_dir / f"backup-{timezone.now().strftime('%Y%m%d-%H%M%S')}.json"
        with filename.open('w', encoding='utf-8') as handle:
            call_command('dumpdata', 'corematoshree', '--natural-foreign', '--natural-primary', indent=2, stdout=handle)
        self.stdout.write(self.style.SUCCESS(f'Backup created: {filename}'))
