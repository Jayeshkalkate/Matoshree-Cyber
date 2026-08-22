import os
import django
from datetime import datetime, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Matoshree.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from corematoshree.models import (
    Service, ServiceCharge, Appointment, Announcement, Contact,
    DownloadForm, FAQ, Gallery, GovernmentScheme, JobNotification,
    PaymentLog, PaymentSettings, RequiredDocument, Review, TeamMember,
    Application
)

User = get_user_model()

# Helper to avoid duplicates
def get_or_create(klass, defaults=None, **kwargs):
    obj, created = klass.objects.get_or_create(defaults=defaults or {}, **kwargs)
    if created:
        print(f"Created {klass.__name__}: {obj}")
    else:
        print(f"Skipped {klass.__name__} (already exists): {obj}")
    return obj

# 1. Services
service_data = [
    {"name": "Printing", "category": "Printing", "description": "Black and white and color printing", "active": True, "icon": "print", "icon_color": "#00d4ff", "payment_required": True},
    {"name": "Photocopy", "category": "Printing", "description": "High-speed photocopying", "active": True, "icon": "copy", "icon_color": "#ff6b35", "payment_required": True},
    {"name": "Scanning", "category": "Document", "description": "Scan documents to PDF or image", "active": True, "icon": "scan", "icon_color": "#a855f7", "payment_required": True},
    {"name": "Aadhaar Services", "category": "Government", "description": "Aadhaar enrollment and updates", "active": True, "icon": "id-card", "icon_color": "#22d3ee", "payment_required": False},
    {"name": "PAN Card Application", "category": "Government", "description": "Apply for new PAN card", "active": True, "icon": "credit-card", "icon_color": "#f97316", "payment_required": True},
    {"name": "Passport Services", "category": "Government", "description": "Passport application assistance", "active": True, "icon": "passport", "icon_color": "#eab308", "payment_required": True},
    {"name": "Internet Cafe", "category": "Internet", "description": "High-speed internet access", "active": True, "icon": "wifi", "icon_color": "#00f0ff", "payment_required": True},
    {"name": "Lamination", "category": "Document", "description": "Document lamination", "active": True, "icon": "file-alt", "icon_color": "#ff2d95", "payment_required": True},
]

for sdata in service_data:
    get_or_create(Service, defaults=sdata, name=sdata["name"])

# 2. Service Charges
charges = {
    "Printing": 10.00,
    "Photocopy": 3.00,
    "Scanning": 15.00,
    "Aadhaar Services": 50.00,
    "PAN Card Application": 100.00,
    "Passport Services": 200.00,
    "Internet Cafe": 30.00,
    "Lamination": 20.00,
}
for name, amount in charges.items():
    service = Service.objects.filter(name=name).first()
    if service:
        sc, created = ServiceCharge.objects.get_or_create(
            service=service,
            defaults={'charge': Decimal(str(amount))}
        )
        if created:
            print(f"Created ServiceCharge: {service.name} - Rs.{amount}")
        else:
            print(f"Skipped ServiceCharge (already exists): {service.name}")

# 3. Announcements
announcements = [
    {"title": "New Service: Lamination", "category": "General", "description": "We now offer lamination for documents.", "is_urgent": False},
    {"title": "PAN Card Deadline Extended", "category": "Government Scheme", "description": "Apply for PAN card before 31 Dec.", "is_urgent": True},
    {"title": "Holiday Notice: Diwali", "category": "Holiday", "description": "Closed on 24th October for Diwali.", "is_urgent": False},
]
for ann in announcements:
    get_or_create(Announcement, defaults=ann, title=ann["title"])

# 4. FAQs
faqs = [
    {"question": "What are your business hours?", "answer": "Monday-Saturday: 9 AM - 8 PM; Sunday: 10 AM - 2 PM."},
    {"question": "Do you provide passport photos?", "answer": "Yes, we provide passport-size photos with printing."},
    {"question": "Can I pay online?", "answer": "Yes, we accept UPI and cash."},
]
for faq in faqs:
    get_or_create(FAQ, defaults=faq, question=faq["question"])

# 5. Required Documents
required_docs = [
    {"service_name": "PAN Card Application", "doc_name": "Aadhaar Card"},
    {"service_name": "PAN Card Application", "doc_name": "Passport size photo"},
    {"service_name": "Passport Services", "doc_name": "Aadhaar Card"},
    {"service_name": "Passport Services", "doc_name": "Voter ID"},
    {"service_name": "Aadhaar Services", "doc_name": "Proof of Identity"},
    {"service_name": "Aadhaar Services", "doc_name": "Proof of Address"},
]
for rd in required_docs:
    service = Service.objects.filter(name=rd["service_name"]).first()
    if service:
        get_or_create(RequiredDocument, defaults={'document_name': rd["doc_name"]}, service=service, document_name=rd["doc_name"])
    else:
        print(f"Service '{rd['service_name']}' not found for RequiredDocument.")

# 6. Team Members
team = [
    {"name": "John Doe", "designation": "Manager", "bio": "15 years experience in cyber services.", "order": 1, "is_active": True},
    {"name": "Jane Smith", "designation": "Technical Assistant", "bio": "Expert in government portals.", "order": 2, "is_active": True},
    {"name": "Rajesh Kumar", "designation": "Customer Support", "bio": "Friendly and helpful.", "order": 3, "is_active": True},
]
for tm in team:
    get_or_create(TeamMember, defaults=tm, name=tm["name"])

# 7. Government Schemes
schemes = [
    {"title": "Pradhan Mantri Awas Yojana", "description": "Affordable housing for all", "eligibility": "Low-income families", "status": "active", "provider": "central", "department": "Housing"},
    {"title": "Maharashtra Udyog Sadhana", "description": "Entrepreneurship scheme", "eligibility": "Youth below 35", "status": "ongoing", "provider": "state", "department": "Industries"},
    {"title": "Digital India Program", "description": "Digital literacy initiative", "eligibility": "All citizens", "status": "active", "provider": "central", "department": "IT"},
]
for sch in schemes:
    get_or_create(GovernmentScheme, defaults=sch, title=sch["title"])

# 8. Job Notifications
jobs = [
    {"title": "Clerk Vacancy", "organization": "Maharashtra Government", "last_date": timezone.now().date() + timedelta(days=30), "apply_link": "https://example.com", "description": "Apply for clerk posts", "icon": "briefcase"},
    {"title": "Assistant Manager", "organization": "Bank of India", "last_date": timezone.now().date() + timedelta(days=15), "apply_link": "https://bank.com", "description": "Banking sector job", "icon": "building"},
]
for job in jobs:
    get_or_create(JobNotification, defaults=job, title=job["title"])

# 9. Payment Settings (singleton)
ps, created = PaymentSettings.objects.get_or_create(
    is_active=True,
    defaults={
        'upi_id': 'cybercafe@upi',
        'upi_mobile': '9876543210',
        'payment_instructions': 'Scan QR code to pay.',
        'upi_enabled': True,
        'cash_enabled': True,
    }
)
if created:
    print("Created PaymentSettings")
else:
    print("Skipped PaymentSettings (already exists)")

# 10. Reviews
reviews = [
    {"customer_name": "Amit Sharma", "email": "amit@example.com", "review": "Excellent service! Quick and friendly.", "rating": 5, "approved": True},
    {"customer_name": "Priya Patel", "email": "priya@example.com", "review": "Very helpful staff. Got my PAN card done.", "rating": 4, "approved": True},
]
for rev in reviews:
    get_or_create(Review, defaults=rev, customer_name=rev["customer_name"], email=rev["email"])

# 11. Appointments (sample)
appointments = [
    {"full_name": "Ravi Kumar", "phone": "9876543210", "email": "ravi@example.com", "service_name": "Printing", "appointment_date": timezone.now().date() + timedelta(days=3), "appointment_time": "10:30", "status": "Pending", "message": ""},
    {"full_name": "Sunita Reddy", "phone": "9876543211", "email": "sunita@example.com", "service_name": "PAN Card Application", "appointment_date": timezone.now().date() + timedelta(days=5), "appointment_time": "14:00", "status": "Confirmed", "message": "Bring documents"},
]
for appt in appointments:
    service = Service.objects.filter(name=appt.pop("service_name")).first()
    if service:
        get_or_create(Appointment, defaults=appt, full_name=appt["full_name"], service=service)
    else:
        print(f"Service '{appt.get('service_name')}' not found for Appointment.")

# 12. Create a test user if none exists
if not User.objects.filter(username='testuser').exists():
    User.objects.create_user('testuser', 'test@example.com', 'password123')
    print("Created testuser (password: password123)")
else:
    print("Skipped testuser (already exists)")

print("\nData population complete!")