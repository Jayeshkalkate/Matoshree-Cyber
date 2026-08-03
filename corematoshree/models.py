# =============================================================================
# MODELS – Core data models for the Cyber Café application
# =============================================================================

from django.db import models
from django.core.validators import RegexValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.utils.crypto import get_random_string
import random

# ==========================
# UTR NO Validator
# ==========================
utr_validator = RegexValidator(
    regex=r'^[A-Za-z0-9]{12,16}$',
    message="UTR number must be 12-16 alphanumeric characters."
)

# ==========================
# Phone Validator
# ==========================
phone_validator = RegexValidator(
    regex=r"^\+?1?\d{10,15}$",
    message="Enter a valid phone number (10–15 digits).",
)


# ==========================
# User Model (Custom)
# ==========================
class User(AbstractUser):
    """Custom user model with role and additional fields."""
    ROLE_CHOICES = (
        ("user", "User"),
        ("admin", "Admin"),
        ("superadmin", "Super Admin"),
    )
    role = models.CharField(
        "Role",
        max_length=20,
        choices=ROLE_CHOICES,
        default="user",
        db_index=True,
    )
    phone = models.CharField(
        "Phone",
        max_length=15,
        blank=True,
        validators=[phone_validator],
    )
    address = models.TextField(
        "Address",
        blank=True,
    )

    def __str__(self):
        return self.username

    class Meta:
        indexes = [
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['email']),
        ]


# ==========================
# Service
# ==========================
class Service(models.Model):
    """Service offered by the cyber café."""
    name = models.CharField("Name", max_length=200, db_index=True)
    category = models.CharField("Category", max_length=100, db_index=True)
    description = models.TextField("Description", blank=True)
    active = models.BooleanField("Active", default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_required = models.BooleanField(
        "Payment Required",
        default=False,
        help_text="If enabled, users will be prompted to pay after application submission."
    )
    icon = models.CharField(
        "Icon",
        max_length=50,
        default="cog",
        help_text="Font Awesome icon class (e.g., 'fa-print')",
    )
    icon_color = models.CharField(
        "Icon Color",
        max_length=7,
        default="#00d4ff",
        help_text="Hex color for the icon circle (e.g., #ff6b35)",
    )

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=['active', 'category']),
            models.Index(fields=['name']),
        ]


# ==========================
# Appointment
# ==========================
class Appointment(models.Model):
    """Appointment booking for a service."""
    STATUS = (
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    )

    full_name = models.CharField("Full Name", max_length=150, db_index=True)
    phone = models.CharField("Phone", max_length=15, validators=[phone_validator], db_index=True)
    email = models.EmailField("Email", blank=True, db_index=True)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        verbose_name="Service",
    )
    appointment_date = models.DateField("Appointment Date", db_index=True)
    appointment_time = models.TimeField("Appointment Time")
    message = models.TextField("Message", blank=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS,
        default="Pending",
        db_index=True,
    )
    created_at = models.DateTimeField("Created At", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"
        indexes = [
            models.Index(fields=['status', 'appointment_date']),
            models.Index(fields=['service', 'appointment_date']),
            models.Index(fields=['created_at']),
        ]

    def clean(self):
        if self.appointment_date and self.appointment_date < timezone.localdate():
            raise ValidationError(
                {"appointment_date": "Appointment date cannot be in the past."}
            )
        if self.appointment_time:
            minutes = self.appointment_time.hour * 60 + self.appointment_time.minute
            if minutes < 9 * 60 or minutes > 17 * 60:
                raise ValidationError(
                    {"appointment_time": "Appointment time must be between 09:00 AM and 05:00 PM."}
                )

    def __str__(self):
        return f"{self.full_name} - {self.service.name}"


# ==========================
# Contact
# ==========================
class Contact(models.Model):
    """Contact form submission from users."""
    name = models.CharField("Name", max_length=150, db_index=True)
    email = models.EmailField("Email", db_index=True)
    phone = models.CharField("Phone", max_length=15, validators=[phone_validator], db_index=True)
    subject = models.CharField("Subject", max_length=200)
    message = models.TextField("Message")
    reply = models.TextField("Reply", blank=True, null=True)
    replied = models.BooleanField("Replied", default=False, db_index=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Contact"
        verbose_name_plural = "Contacts"
        indexes = [
            models.Index(fields=['replied', 'created_at']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.name


# ==========================
# Review
# ==========================
class Review(models.Model):
    """Customer review with rating."""
    customer_name = models.CharField("Customer Name", max_length=100, db_index=True)
    email = models.EmailField("Email", blank=True, null=True, db_index=True)
    review = models.TextField("Review")
    rating = models.PositiveSmallIntegerField("Rating", default=5, db_index=True)
    approved = models.BooleanField("Approved", default=False, db_index=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        indexes = [
            models.Index(fields=['approved', 'rating']),
            models.Index(fields=['created_at']),
            models.Index(fields=['approved', '-created_at']),
        ]

    def __str__(self):
        return f"{self.customer_name} ({self.rating}/5)"


# ==========================
# Announcement
# ==========================
class Announcement(models.Model):
    """Announcements/news displayed on the site."""
    CATEGORY = (
        ("General", "General"),
        ("Government Scheme", "Government Scheme"),
        ("Recruitment", "Recruitment"),
        ("Scholarship", "Scholarship"),
        ("Holiday", "Holiday"),
        ("Notice", "Notice"),
    )

    title = models.CharField("Title", max_length=200, db_index=True)
    category = models.CharField("Category", max_length=50, choices=CATEGORY, db_index=True)
    description = models.TextField("Description")
    is_urgent = models.BooleanField("Urgent", default=False, db_index=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        indexes = [
            models.Index(fields=['category', 'created_at']),
            models.Index(fields=['is_urgent']),
        ]

    def __str__(self):
        return self.title


# ==========================
# Gallery
# ==========================
class Gallery(models.Model):
    """Gallery images."""
    CATEGORY = (
        ("Cyber Cafe", "Cyber Cafe"),
        ("Customers", "Customers"),
        ("Certificates", "Certificates"),
        ("Equipment", "Equipment"),
        ("Office", "Office"),
    )

    title = models.CharField("Title", max_length=100)
    category = models.CharField("Category", max_length=50, choices=CATEGORY, db_index=True)
    image = models.ImageField("Image", upload_to="gallery/")

    class Meta:
        verbose_name = "Gallery Image"
        verbose_name_plural = "Gallery Images"
        indexes = [
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.title


# ==========================
# Service Charge
# ==========================
class ServiceCharge(models.Model):
    """Pricing for a service."""
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        verbose_name="Service",
    )
    charge = models.DecimalField(
        "Charge",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Must be greater than or equal to 0."
    )

    class Meta:
        verbose_name = "Service Charge"
        verbose_name_plural = "Service Charges"
        indexes = [
            models.Index(fields=['service']),
        ]
        ordering = ['service__name']

    def __str__(self):
        return f"{self.service.name} - ₹{self.charge}"


# ==========================
# Required Document
# ==========================
class RequiredDocument(models.Model):
    """Documents required for a service."""
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        verbose_name="Service",
    )
    document_name = models.CharField("Document Name", max_length=200, db_index=True)

    class Meta:
        verbose_name = "Required Document"
        verbose_name_plural = "Required Documents"
        indexes = [
            models.Index(fields=['service', 'document_name']),
        ]
        unique_together = [['service', 'document_name']]
        ordering = ['service__name', 'document_name']

    def __str__(self):
        return f"{self.service.name} - {self.document_name}"


# ==========================
# Download Form (PDF)
# ==========================
class DownloadForm(models.Model):
    """Uploaded PDF forms available for download."""
    title = models.CharField("Title", max_length=200, db_index=True)
    category = models.CharField("Category", max_length=100, db_index=True)
    pdf = models.FileField("PDF", upload_to="forms/")
    uploaded_at = models.DateTimeField("Uploaded At", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Download Form"
        verbose_name_plural = "Download Forms"
        indexes = [
            models.Index(fields=['category', 'uploaded_at']),
        ]

    def __str__(self):
        return self.title


# ==========================
# Government Scheme
# ==========================
class GovernmentScheme(models.Model):
    """Government schemes information."""
    title = models.CharField("Title", max_length=200, db_index=True)
    description = models.TextField("Description")
    eligibility = models.TextField("Eligibility", blank=True)
    last_date = models.DateField("Last Date", null=True, blank=True, db_index=True)
    image = models.ImageField("Image", upload_to="schemes/", blank=True, null=True)

    class Meta:
        verbose_name = "Government Scheme"
        verbose_name_plural = "Government Schemes"
        indexes = [
            models.Index(fields=['last_date']),
        ]

    def __str__(self):
        return self.title


# ==========================
# Job Notification
# ==========================
class JobNotification(models.Model):
    """Job openings and notifications."""
    title = models.CharField("Title", max_length=200, db_index=True)
    organization = models.CharField("Organization", max_length=200, db_index=True)
    last_date = models.DateField("Last Date", db_index=True)
    apply_link = models.URLField("Apply Link", blank=True)
    description = models.TextField("Description")
    icon = models.CharField(
        "Icon",
        max_length=50,
        default="briefcase",
        help_text="Font Awesome icon (e.g. 'fa-briefcase')",
    )

    class Meta:
        verbose_name = "Job Notification"
        verbose_name_plural = "Job Notifications"
        indexes = [
            models.Index(fields=['last_date']),
            models.Index(fields=['organization']),
        ]

    def __str__(self):
        return self.title


# ==========================
# FAQ
# ==========================
class FAQ(models.Model):
    """Frequently asked questions."""
    question = models.CharField("Question", max_length=300, db_index=True)
    answer = models.TextField("Answer")

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        indexes = [
            models.Index(fields=['question']),
        ]

    def __str__(self):
        return self.question


# ==========================
# Business Info (Singleton)
# ==========================
class BusinessInfo(models.Model):
    """Business information – singleton model."""
    business_name = models.CharField("Business Name", max_length=200)
    welcome_message = models.TextField("Welcome Message")
    address = models.TextField("Address")
    phone = models.CharField("Phone", max_length=15, validators=[phone_validator])
    whatsapp = models.CharField("WhatsApp", max_length=15, validators=[phone_validator])
    email = models.EmailField("Email")
    google_map = models.TextField(
        "Google Map",
        help_text="Paste Google Maps Embed Code",
    )
    business_hours = models.TextField("Business Hours")
    registration_number = models.CharField(
        "Registration Number",
        max_length=100,
        blank=True,
        help_text="e.g. UDYAM-XX-00-0000000",
    )
    certifications = models.TextField(
        "Certifications / Authorizations",
        blank=True,
        help_text="Enter each certification on a new line.",
    )
    logo = models.ImageField(
        "Logo",
        upload_to="business/",
        blank=True,
        null=True,
        help_text="Business logo for receipts and branding."
    )
    gstin = models.CharField(
        "GSTIN",
        max_length=20,
        blank=True,
        help_text="GST Identification Number (if applicable)"
    )

    def save(self, *args, **kwargs):
        if self.pk:
            BusinessInfo.objects.exclude(pk=self.pk).delete()
        else:
            BusinessInfo.objects.all().delete()
        super().save(*args, **kwargs)
        cache.delete('business_info')

    class Meta:
        verbose_name = "Business Information"
        verbose_name_plural = "Business Information"


# ==========================
# Application
# ==========================

class Application(models.Model):
    """User application for a service."""

    PAYMENT_APP_CHOICES = (
        ('gpay', 'Google Pay'),
        ('phonepe', 'PhonePe'),
        ('paytm', 'Paytm'),
        ('bhim', 'BHIM'),
        ('upi', 'Other UPI App'),
        ('other', 'Other'),
    )
    
    service_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    razorpay_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    gst_on_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Razorpay fields
    razorpay_order_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Razorpay Order ID",
        db_index=True
    )
    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Razorpay Payment ID",
        db_index=True
    )
    razorpay_signature = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Razorpay Signature"
    )

    utr_number = models.CharField(
        "UTR Number",
        max_length=50,
        blank=True,
        validators=[utr_validator],
        help_text="Unique Transaction Reference (if available)"
    )

    payment_app = models.CharField(
        "Payment App",
        max_length=20,
        choices=PAYMENT_APP_CHOICES,
        blank=True,
        null=True,
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("review", "Under Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    PAYMENT_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    )

    PAYMENT_METHOD_CHOICES = (
        ("upi", "UPI"),
        ("cash", "Cash"),
        ("manual", "Manual"),
        ("razorpay", "Razorpay"),   # Added Razorpay method
    )

    # --- Core fields ---
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="User")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name="Service")
    full_name = models.CharField("Full Name", max_length=150, db_index=True)
    phone = models.CharField("Phone", max_length=15, validators=[phone_validator], db_index=True)
    email = models.EmailField("Email", db_index=True)
    address = models.TextField("Address")
    extra_data = models.JSONField("Extra Data", blank=True, null=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    created_at = models.DateTimeField("Created At", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True, db_index=True)

    # --- Payment fields ---
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending",
        db_index=True,
        verbose_name="Payment Status"
    )
    payment_transaction_id = models.CharField(max_length=100, blank=True, verbose_name="Payment Transaction ID")
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="upi",
        blank=True,
        verbose_name="Payment Method"
    )
    payment_date = models.DateTimeField(null=True, blank=True, verbose_name="Payment Date")
    receipt_number = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name="Receipt Number")

    def generate_receipt_number(self):
        """
        Generates a receipt number. If the instance already has an ID, uses that.
        Otherwise, falls back to a random 8-character alphanumeric string.
        """
        from django.utils import timezone
        now = timezone.now()
        base = f"RCP-{now.strftime('%Y%m%d')}"
        if self.id:
            return f"{base}-{self.id:04d}"
        else:
            return f"{base}-{get_random_string(8, allowed_chars='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')}"

    def clean(self):
        if self.payment_app and not self.utr_number:
            raise ValidationError({"utr_number": "UTR number is required when a payment app is selected."})

    def __str__(self):
        return f"{self.full_name} – {self.service.name}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Application"
        verbose_name_plural = "Applications"
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['service', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['payment_status']),
        ]


# ==========================
# Document Upload
# ==========================
class DocumentUpload(models.Model):
    """Uploaded documents for an application."""
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Application"
    )
    document_name = models.CharField("Document Name", max_length=200, db_index=True)
    file = models.FileField("File", upload_to="applications/%Y/%m/%d/")
    is_mandatory = models.BooleanField("Mandatory", default=True, db_index=True)
    uploaded_at = models.DateTimeField("Uploaded At", auto_now_add=True, db_index=True)
    verified = models.BooleanField("Verified by Admin", default=False, db_index=True)

    class Meta:
        verbose_name = "Document Upload"
        verbose_name_plural = "Document Uploads"
        indexes = [
            models.Index(fields=['application', 'verified']),
            models.Index(fields=['document_name']),
            models.Index(fields=['is_mandatory']),
        ]

    def __str__(self):
        return f"{self.document_name} – {self.application.full_name}"


# ==========================
# Team Member
# ==========================
class TeamMember(models.Model):
    """Team member profile."""
    name = models.CharField("Name", max_length=100, db_index=True)
    designation = models.CharField("Designation", max_length=200)
    bio = models.TextField("Bio", blank=True)
    photo = models.ImageField("Photo", upload_to="team/", blank=True, null=True)
    order = models.PositiveIntegerField("Order", default=0, help_text="Lower numbers appear first.")
    is_active = models.BooleanField("Active", default=True, db_index=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Team Member"
        verbose_name_plural = "Team Members"
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return self.name


# ==========================
# Payment Settings (Singleton) – UPI + Cash only
# ==========================
class PaymentSettings(models.Model):
    """Payment gateway configuration – singleton."""
    upi_id = models.CharField("UPI ID", max_length=100, blank=True, help_text="e.g. example@upi")
    upi_mobile = models.CharField("UPI Mobile", max_length=15, blank=True)
    qr_code = models.ImageField("QR Code", upload_to="payments/", blank=True, null=True)
    payment_instructions = models.TextField("Instructions", blank=True, default="Scan QR code and pay using any UPI app.")
    is_active = models.BooleanField("Active", default=True)

    # Gateway toggles
    upi_enabled = models.BooleanField("Enable UPI Payment", default=True)
    cash_enabled = models.BooleanField("Enable Cash Payment", default=False)

    def save(self, *args, **kwargs):
        # Singleton logic
        if self.pk:
            PaymentSettings.objects.exclude(pk=self.pk).delete()
        else:
            PaymentSettings.objects.all().delete()
        # Ensure only one active setting
        if self.is_active:
            PaymentSettings.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
        cache.delete('payment_settings')

    def __str__(self):
        return "Payment Settings" if self.is_active else "Payment Settings (Inactive)"

    class Meta:
        verbose_name = "Payment Setting"
        verbose_name_plural = "Payment Settings"


# ==========================
# Payment Log (for audit trail)
# ==========================
class PaymentLog(models.Model):
    """Audit trail for payment events."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="payment_logs", verbose_name="Application")
    event_type = models.CharField(
        max_length=50,
        choices=(
            ('created', 'Order Created'),
            ('captured', 'Payment Captured'),
            ('failed', 'Payment Failed'),
            ('refunded', 'Payment Refunded'),
            ('webhook_received', 'Webhook Received'),
            ('manual_confirmed', 'Manually Confirmed'),
        ),
        db_index=True,
        verbose_name="Event Type"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Amount")
    # Audit fields
    ip_address = models.GenericIPAddressField("IP Address", blank=True, null=True)
    user_agent = models.CharField("User Agent", max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Payment Log"
        verbose_name_plural = "Payment Logs"
        indexes = [
            models.Index(fields=['application', 'event_type']),
        ]

    def __str__(self):
        return f"{self.application.full_name} – {self.event_type} – {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
