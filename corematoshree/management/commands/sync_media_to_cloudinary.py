import os
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from cloudinary.uploader import upload
from ...models import Gallery  # adjust

class Command(BaseCommand):
    def handle(self, *args, **options):
        for obj in Gallery.objects.all():
            if obj.image and obj.image.name:
                try:
                    if os.path.exists(obj.image.path):
                        with open(obj.image.path, 'rb') as f:
                            upload_result = upload(f, public_id=obj.image.name)
                            self.stdout.write(f"Uploaded {obj.image.name}")
                    else:
                        self.stdout.write(self.style.WARNING(f"File {obj.image.name} not found, skipping."))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error: {e}"))