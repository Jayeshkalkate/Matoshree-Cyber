import csv
from django.core.management.base import BaseCommand
from django.core.files import File
from corematoshree.models import DownloadForm
import os

# without img and pdf
# python manage.py import_forms data/forms.csv

# With img and pdf
# python manage.py import_forms data/forms.csv --pdf_dir data/pdfs

class Command(BaseCommand):
    help = 'Import Download Forms from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file')
        parser.add_argument('--pdf_dir', type=str, help='Directory containing PDF files (optional)')

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        pdf_dir = options.get('pdf_dir', None)

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                pdf_file = None
                if pdf_dir and row.get('pdf'):
                    pdf_path = os.path.join(pdf_dir, row['pdf'])
                    if os.path.exists(pdf_path):
                        with open(pdf_path, 'rb') as pdf:
                            pdf_file = File(pdf, name=row['pdf'])

                form = DownloadForm(
                    title=row['title'],
                    category=row.get('category', 'General'),
                )
                if pdf_file:
                    form.pdf.save(row['pdf'], pdf_file, save=False)
                form.save()
                count += 1
                self.stdout.write(f"Imported: {form.title}")

        self.stdout.write(self.style.SUCCESS(f"Successfully imported {count} forms."))