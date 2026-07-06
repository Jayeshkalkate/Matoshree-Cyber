from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _   # <-- added

# ==========================
# User
# ==========================
class User(AbstractUser):
    ROLE_CHOICES = (
        ('user', _('User')),
        ('admin', _('Admin')),
        ('superadmin', _('Super Admin')),
    )
    role = models.CharField(
        _("Role"),
        max_length=20,
        choices=ROLE_CHOICES,
        default='user'
    )
    phone = models.CharField(
        _("Phone"),
        max_length=15,
        blank=True
    )
    address = models.TextField(
        _("Address"),
        blank=True
    )

    def __str__(self):
        return self.username

# ==========================
# Validators
# ==========================
phone_validator = RegexValidator(
    regex=r'^\+?1?\d{10,15}$',
    message=_("Enter a valid phone number (10-15 digits).")
)

# ==========================
# Services
# ==========================
class Service(models.Model):
    name = models.CharField(
        _("Name"),
        max_length=200
    )
    category = models.CharField(
        _("Category"),
        max_length=100
    )
    description = models.TextField(
        _("Description"),
        blank=True
    )
    active = models.BooleanField(
        _("Active"),
        default=True
    )
    icon = models.CharField(
        _("Icon"),
        max_length=50,
        default="cog",
        help_text=_("Font Awesome icon class (e.g., 'fa-print')")
    )
    icon_color = models.CharField(
        _("Icon Color"),
        max_length=7,
        default='#00d4ff',
        help_text=_("Hex color for the icon circle (e.g., #ff6b35)")
    )

    def __str__(self):
        return self.name

# ==========================
# Appointment
# ==========================
class Appointment(models.Model):
    STATUS = (
        ("Pending", _("Pending")),
        ("Confirmed", _("Confirmed")),
        ("Completed", _("Completed")),
        ("Cancelled", _("Cancelled")),
    )

    full_name = models.CharField(
        _("Full Name"),
        max_length=150
    )
    phone = models.CharField(
        _("Phone"),
        max_length=15,
        validators=[phone_validator]
    )
    email = models.EmailField(
        _("Email"),
        blank=True
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        verbose_name=_("Service")
    )
    appointment_date = models.DateField(
        _("Appointment Date")
    )
    appointment_time = models.TimeField(
        _("Appointment Time")
    )
    message = models.TextField(
        _("Message"),
        blank=True
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS,
        default="Pending"
    )
    created_at = models.DateTimeField(
        _("Created At"),
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Appointment")
        verbose_name_plural = _("Appointments")

    def clean(self):
        if self.appointment_date is None:
            return
        if self.appointment_date < timezone.localdate():
            raise ValidationError(
                {"appointment_date": _("Appointment date cannot be in the past.")}
            )
        if self.appointment_time is None:
            return

    def __str__(self):
        return f"{self.full_name} - {self.service.name}"

# ==========================
# Contact
# ==========================
class Contact(models.Model):
    name = models.CharField(
        _("Name"),
        max_length=150
    )
    email = models.EmailField(
        _("Email")
    )
    phone = models.CharField(
        _("Phone"),
        max_length=15,
        validators=[phone_validator]
    )
    subject = models.CharField(
        _("Subject"),
        max_length=200
    )
    message = models.TextField(
        _("Message")
    )
    replied = models.BooleanField(
        _("Replied"),
        default=False
    )
    created_at = models.DateTimeField(
        _("Created At"),
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Contact")
        verbose_name_plural = _("Contacts")

    def __str__(self):
        return self.name

# ==========================
# Reviews
# ==========================
class Review(models.Model):
    customer_name = models.CharField(
        _("Customer Name"),
        max_length=100
    )
    email = models.EmailField(
        _("Email"),
        blank=True,
        null=True
    )
    review = models.TextField(
        _("Review")
    )
    rating = models.PositiveSmallIntegerField(
        _("Rating"),
        default=5
    )
    approved = models.BooleanField(
        _("Approved"),
        default=True
    )
    created_at = models.DateTimeField(
        _("Created At"),
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Review")
        verbose_name_plural = _("Reviews")

    def __str__(self):
        return f"{self.customer_name} ({self.rating}/5)"

# ==========================
# Announcements
# ==========================
class Announcement(models.Model):
    CATEGORY = (
        ("Government Scheme", _("Government Scheme")),
        ("Recruitment", _("Recruitment")),
        ("Scholarship", _("Scholarship")),
        ("Holiday", _("Holiday")),
        ("Notice", _("Notice")),
    )

    title = models.CharField(
        _("Title"),
        max_length=200
    )
    category = models.CharField(
        _("Category"),
        max_length=50,
        choices=CATEGORY
    )
    description = models.TextField(
        _("Description")
    )
    created_at = models.DateTimeField(
        _("Created At"),
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Announcement")
        verbose_name_plural = _("Announcements")

    def __str__(self):
        return self.title

# ==========================
# Gallery
# ==========================
class Gallery(models.Model):
    CATEGORY = (
        ("Cyber Cafe", _("Cyber Cafe")),
        ("Customers", _("Customers")),
        ("Certificates", _("Certificates")),
        ("Equipment", _("Equipment")),
        ("Office", _("Office")),
    )

    title = models.CharField(
        _("Title"),
        max_length=100
    )
    category = models.CharField(
        _("Category"),
        max_length=50,
        choices=CATEGORY
    )
    image = models.ImageField(
        _("Image"),
        upload_to="gallery/"
    )

    class Meta:
        verbose_name = _("Gallery Image")
        verbose_name_plural = _("Gallery Images")

    def __str__(self):
        return self.title

# ==========================
# Service Charges
# ==========================
class ServiceCharge(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        verbose_name=_("Service")
    )
    charge = models.DecimalField(
        _("Charge"),
        max_digits=8,
        decimal_places=2
    )

    class Meta:
        verbose_name = _("Service Charge")
        verbose_name_plural = _("Service Charges")

    def __str__(self):
        return f"{self.service.name} - ₹{self.charge}"

# ==========================
# Required Documents
# ==========================
class RequiredDocument(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        verbose_name=_("Service")
    )
    document_name = models.CharField(
        _("Document Name"),
        max_length=200
    )

    class Meta:
        verbose_name = _("Required Document")
        verbose_name_plural = _("Required Documents")

    def __str__(self):
        return f"{self.service.name} - {self.document_name}"

# ==========================
# Download Forms
# ==========================
class DownloadForm(models.Model):
    title = models.CharField(
        _("Title"),
        max_length=200
    )
    category = models.CharField(
        _("Category"),
        max_length=100
    )
    pdf = models.FileField(
        _("PDF"),
        upload_to="forms/"
    )
    uploaded_at = models.DateTimeField(
        _("Uploaded At"),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _("Download Form")
        verbose_name_plural = _("Download Forms")

    def __str__(self):
        return self.title

# ==========================
# Government Schemes
# ==========================
class GovernmentScheme(models.Model):
    title = models.CharField(
        _("Title"),
        max_length=200
    )
    description = models.TextField(
        _("Description")
    )
    eligibility = models.TextField(
        _("Eligibility"),
        blank=True
    )
    last_date = models.DateField(
        _("Last Date"),
        null=True,
        blank=True
    )
    image = models.ImageField(
        _("Image"),
        upload_to='schemes/',
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = _("Government Scheme")
        verbose_name_plural = _("Government Schemes")

    def __str__(self):
        return self.title

# ==========================
# Job Notifications
# ==========================
class JobNotification(models.Model):
    title = models.CharField(
        _("Title"),
        max_length=200
    )
    organization = models.CharField(
        _("Organization"),
        max_length=200
    )
    last_date = models.DateField(
        _("Last Date")
    )
    apply_link = models.URLField(
        _("Apply Link"),
        blank=True
    )
    description = models.TextField(
        _("Description")
    )
    icon = models.CharField(
        _("Icon"),
        max_length=50,
        default='briefcase',
        help_text=_("Font Awesome icon (e.g. 'fa-briefcase')")
    )

    class Meta:
        verbose_name = _("Job Notification")
        verbose_name_plural = _("Job Notifications")

    def __str__(self):
        return self.title

# ==========================
# FAQs
# ==========================
class FAQ(models.Model):
    question = models.CharField(
        _("Question"),
        max_length=300
    )
    answer = models.TextField(
        _("Answer")
    )

    class Meta:
        verbose_name = _("FAQ")
        verbose_name_plural = _("FAQs")

    def __str__(self):
        return self.question

# ==========================
# Business Information (Singleton)
# ==========================
class BusinessInfo(models.Model):
    business_name = models.CharField(
        _("Business Name"),
        max_length=200
    )
    logo = models.ImageField(
        _("Logo"),
        upload_to="logo/",
        blank=True,
        null=True
    )
    welcome_message = models.TextField(
        _("Welcome Message")
    )
    address = models.TextField(
        _("Address")
    )
    phone = models.CharField(
        _("Phone"),
        max_length=15,
        validators=[phone_validator]
    )
    whatsapp = models.CharField(
        _("WhatsApp"),
        max_length=15,
        validators=[phone_validator]
    )
    email = models.EmailField(
        _("Email")
    )
    google_map = models.TextField(
        _("Google Map"),
        help_text=_("Paste Google Maps Embed Code")
    )
    business_hours = models.TextField(
        _("Business Hours")
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            existing = BusinessInfo.objects.first()
            if existing:
                self.pk = existing.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        instance = cls.objects.first()
        if not instance:
            instance = cls()
            instance.save()
        return instance

    class Meta:
        verbose_name = _("Business Information")
        verbose_name_plural = _("Business Information")

    def __str__(self):
        return self.business_name
    
