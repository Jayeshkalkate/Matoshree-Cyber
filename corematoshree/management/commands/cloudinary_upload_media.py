# corematoshree/management/commands/cloudinary_upload_media.py

# python manage.py cloudinary_upload_media
# python manage.py cloudinary_upload_media --dry-run

import os
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.apps import apps
from django.db import transaction
from cloudinary_storage.storage import MediaCloudinaryStorage


class Command(BaseCommand):
    help = 'Upload all media files to Cloudinary and update database paths'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be uploaded without actually uploading',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        # Check if Cloudinary storage is active
        if not isinstance(default_storage, MediaCloudinaryStorage):
            self.stderr.write(self.style.ERROR(
                'Cloudinary storage is not active. Set DEFAULT_FILE_STORAGE to cloudinary_storage.storage.MediaCloudinaryStorage'
            ))
            return

        # Get all models that have FileField or ImageField
        models_with_files = []
        for model in apps.get_models():
            fields = [f for f in model._meta.get_fields() if f.is_relation is False and hasattr(f, 'upload_to')]
            if fields:
                models_with_files.append((model, fields))

        if not models_with_files:
            self.stdout.write('No models with file fields found.')
            return

        total_uploaded = 0
        total_failed = 0

        for model, fields in models_with_files:
            self.stdout.write(f'Processing {model.__name__}...')
            for obj in model.objects.all():
                for field in fields:
                    file_field = getattr(obj, field.name)
                    if file_field and file_field.name:
                        # The file already has a URL; if it's not a Cloudinary URL, we need to upload it.
                        # Check if it's already on Cloudinary (starts with "http" and contains "cloudinary")
                        current_url = file_field.url if hasattr(file_field, 'url') else None
                        if current_url and 'cloudinary' in current_url:
                            self.stdout.write(f'  - Skipping {obj} {field.name}: already on Cloudinary')
                            continue

                        # Read the file from current storage (local)
                        try:
                            with default_storage.open(file_field.name, 'rb') as f:
                                file_content = f.read()
                            file_name = os.path.basename(file_field.name)

                            if dry_run:
                                self.stdout.write(f'  [DRY RUN] Would upload {file_name} for {obj}')
                                continue

                            # Upload to Cloudinary
                            new_name = default_storage.save(file_field.name, ContentFile(file_content))
                            # The field now points to Cloudinary, but we need to update the database
                            # to reflect the new storage path (which is automatic if the field is updated)
                            # Actually, default_storage.save returns the new name, but the field already contains that?
                            # Best practice: update the field with the new name (or just save the object)
                            # However, the field is already set; we just need to save the object to trigger the update.
                            # But the field value hasn't changed, so we force an update:
                            setattr(obj, field.name, file_field)  # re-assign to trigger save
                            obj.save(update_fields=[field.name])
                            total_uploaded += 1
                            self.stdout.write(self.style.SUCCESS(f'  - Uploaded {file_name} for {obj}'))

                        except Exception as e:
                            total_failed += 1
                            self.stderr.write(self.style.ERROR(f'  - Failed to upload {file_field.name}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'Upload complete. Uploaded: {total_uploaded}, Failed: {total_failed}'
        ))