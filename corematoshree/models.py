from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
    
# ==========================
# User
# ==========================
class User(AbstractUser):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('admin', 'Admin'),
        ('superadmin', 'Super Admin'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.username
    
# ==========================
# Validators
# ==========================
phone_validator = RegexValidator(
    regex=r'^\+?1?\d{10,15}$',
    message="Enter a valid phone number (10-15 digits)."
)


# ==========================
# Services
# ==========================
class Service(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    icon = models.CharField(
        max_length=50,
        default="cog",
        help_text="Font Awesome icon class (e.g., 'fa-print')"
    )

    def __str__(self):
        return self.name


# ==========================
# Appointment
# ==========================
class Appointment(models.Model):
    STATUS = (
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    )

    full_name = models.CharField(max_length=150)
    phone = models.CharField(
        max_length=15,
        validators=[phone_validator]
    )
    email = models.EmailField(blank=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="Pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.appointment_date is None:
            return
        
        if self.appointment_date < timezone.localdate():
            raise ValidationError(
                {"appointment_date": "Appointment date cannot be in the past."}
            )
            
        # Optional: Add time validation
        if self.appointment_time is None:
            return

    def __str__(self):
        return f"{self.full_name} - {self.service.name}"


# ==========================
# Contact
# ==========================
class Contact(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(
        max_length=15,
        validators=[phone_validator]
    )
    subject = models.CharField(max_length=200)
    message = models.TextField()
    replied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


# ==========================
# Reviews
# ==========================
class Review(models.Model):
    customer_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)   # <-- NEW FIELD
    review = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5)
    approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer_name} ({self.rating}/5)"


# ==========================
# Announcements
# ==========================
class Announcement(models.Model):
    CATEGORY = (
        ("Government Scheme", "Government Scheme"),
        ("Recruitment", "Recruitment"),
        ("Scholarship", "Scholarship"),
        ("Holiday", "Holiday"),
        ("Notice", "Notice"),
    )

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


# ==========================
# Gallery
# ==========================
class Gallery(models.Model):
    CATEGORY = (
        ("Cyber Cafe", "Cyber Cafe"),
        ("Customers", "Customers"),
        ("Certificates", "Certificates"),
        ("Equipment", "Equipment"),
        ("Office", "Office"),
    )

    title = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY)
    image = models.ImageField(upload_to="gallery/")

    def __str__(self):
        return self.title


# ==========================
# Service Charges
# ==========================
class ServiceCharge(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    charge = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.service.name} - ₹{self.charge}"


# ==========================
# Required Documents
# ==========================
class RequiredDocument(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    document_name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.service.name} - {self.document_name}"


# ==========================
# Download Forms
# ==========================
class DownloadForm(models.Model):
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    pdf = models.FileField(upload_to="forms/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# ==========================
# Government Schemes
# ==========================
class GovernmentScheme(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    eligibility = models.TextField(blank=True)
    last_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.title


# ==========================
# Job Notifications
# ==========================
class JobNotification(models.Model):
    title = models.CharField(max_length=200)
    organization = models.CharField(max_length=200)
    last_date = models.DateField()
    apply_link = models.URLField(blank=True)
    description = models.TextField()

    def __str__(self):
        return self.title


# ==========================
# FAQs
# ==========================
class FAQ(models.Model):
    question = models.CharField(max_length=300)
    answer = models.TextField()

    def __str__(self):
        return self.question


# ==========================
# Business Information (Singleton)
# ==========================
class BusinessInfo(models.Model):
    business_name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to="logo/", blank=True, null=True)
    welcome_message = models.TextField()

    address = models.TextField()

    phone = models.CharField(
        max_length=15,
        validators=[phone_validator]
    )

    whatsapp = models.CharField(
        max_length=15,
        validators=[phone_validator]
    )

    email = models.EmailField()

    google_map = models.TextField(
        help_text="Paste Google Maps Embed Code"
    )

    business_hours = models.TextField()

    def save(self, *args, **kwargs):
        """
        Enforce singleton: if an instance already exists, update it instead of creating a new one.
        """
        if not self.pk:
            existing = BusinessInfo.objects.first()
            if existing:
                self.pk = existing.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        """
        Retrieve the singleton instance. If none exists, create a blank one.
        """
        instance = cls.objects.first()
        if not instance:
            instance = cls()
            instance.save()
        return instance

    def __str__(self):
        return self.business_name
    