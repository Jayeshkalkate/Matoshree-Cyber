"""Encrypt document files uploaded before EncryptedDocumentStorage was enabled."""
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from corematoshree.models import DocumentUpload


class Command(BaseCommand):
    help = "Encrypt legacy application documents at rest (run after setting a stable FILE_ENCRYPTION_KEY)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List legacy document records without changing them.")

    def handle(self, *args, **options):
        documents = DocumentUpload.objects.exclude(file="").exclude(file__startswith="encrypted-documents/").order_by("pk")
        total = documents.count()
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"{total} document(s) require encryption."))
            return

        updated = 0
        failed = 0
        for document in documents.iterator():
            old_name = document.file.name
            try:
                with document.file.open("rb") as original:
                    plaintext = original.read()
                storage = document.file.storage
                encrypted_name = storage.save(old_name, ContentFile(plaintext, name=old_name))
                if not storage.is_encrypted_name(encrypted_name):
                    raise CommandError(f"Storage did not return an encrypted filename for document {document.pk}.")
                with transaction.atomic():
                    DocumentUpload.objects.filter(pk=document.pk).update(file=encrypted_name)
                storage.delete(old_name)
                updated += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"Could not encrypt document {document.pk}: {type(exc).__name__}"))

        self.stdout.write(self.style.SUCCESS(f"Encrypted {updated} of {total} document(s); failures: {failed}."))
        if failed:
            raise CommandError("Some documents could not be encrypted. Keep a backup and review the reported record IDs.")
