import csv
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from corematoshree.models import GovernmentScheme
import os
from datetime import datetime

# with img and pdf
# python manage.py import_schemes data/schemes.csv

# without img and pdf
# python manage.py import_schemes data/schemes.csv --image_dir data/images

class Command(BaseCommand):
    help = 'Import Government Schemes from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file')
        parser.add_argument('--image_dir', type=str, help='Directory containing image files (optional)')

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        image_dir = options.get('image_dir', None)

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                # Expected columns: title, description, eligibility, last_date, image (filename)
                image_file = None
                if image_dir and row.get('image'):
                    img_path = os.path.join(image_dir, row['image'])
                    if os.path.exists(img_path):
                        with open(img_path, 'rb') as img:
                            image_file = File(img, name=row['image'])

                # Parse date
                last_date = None
                if row.get('last_date'):
                    try:
                        last_date = datetime.strptime(row['last_date'], '%Y-%m-%d').date()
                    except ValueError:
                        self.stdout.write(self.style.WARNING(f"Invalid date format for {row['title']}, skipping date"))

                scheme = GovernmentScheme(
                    title=row['title'],
                    description=row.get('description', ''),
                    eligibility=row.get('eligibility', ''),
                    last_date=last_date,
                )
                if image_file:
                    scheme.image.save(row['image'], image_file, save=False)
                scheme.save()
                count += 1
                self.stdout.write(f"Imported: {scheme.title}")

        self.stdout.write(self.style.SUCCESS(f"Successfully imported {count} schemes."))