import os
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from corematoshree.models import Gallery

class Command(BaseCommand):
    help = 'Remove gallery records with missing image files'

    def handle(self, *args, **options):
        deleted = 0
        for gallery in Gallery.objects.all():
            if gallery.image and not default_storage.exists(gallery.image.name):
                self.stdout.write(f'Deleting gallery #{gallery.id} – {gallery.image.name}')
                gallery.delete()
                deleted += 1
        self.stdout.write(self.style.SUCCESS(f'Removed {deleted} broken gallery entries.'))
        