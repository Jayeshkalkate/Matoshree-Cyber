from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache


# ==========================
# Phone Validator
# ==========================
phone_validator = RegexValidator(
    regex=r"^\+?1?\d{10,15}$",
    message=_("Enter a valid phone number (10–15 digits)."),
)


# ==========================
# User Model (Custom)
# ==========================
class User(AbstractUser):
    ROLE_CHOICES = (
        ("user", _("User")),
        ("admin", _("Admin")),
        ("superadmin", _("Super Admin")),
    )
    role = models.CharField(
        _("Role"),
        max_length=20,
        choices=ROLE_CHOICES,
        default="user",
        db_index=True,
    )
    phone = models.CharField(
        _("Phone"),
        max_length=15,
        blank=True,
        validators=[phone_validator],
    )
    address = models.TextField(
        _("Address"),
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
    name = models.CharField(_("Name"), max_length=200, db_index=True)
    category = models.CharField(_("Category"), max_length=100, db_index=True)
    description = models.TextField(_("Description"), blank=True)
    active = models.BooleanField(_("Active"), default=True, db_index=True)
    icon = models.CharField(
        _("Icon"),
        max_length=50,
        default="cog",
        help_text=_("Font Awesome icon class (e.g., 'fa-print')"),
    )
    icon_color = models.CharField(
        _("Icon Color"),
        max_length=7,
        default="#00d4ff",
        help_text=_("Hex color for the icon circle (e.g., #ff6b35)"),
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
    STATUS = (
        ("Pending", _("Pending")),
        ("Confirmed", _("Confirmed")),
        ("Completed", _("Completed")),
        ("Cancelled", _("Cancelled")),
    )

    full_name = models.CharField(_("Full Name"), max_length=150, db_index=True)
    phone = models.CharField(_("Phone"), max_length=15, validators=[phone_validator], db_index=True)
    email = models.EmailField(_("Email"), blank=True, db_index=True)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        verbose_name=_("Service"),
    )
    appointment_date = models.DateField(_("Appointment Date"), db_index=True)
    appointment_time = models.TimeField(_("Appointment Time"))
    message = models.TextField(_("Message"), blank=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS,
        default="Pending",
        db_index=True,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Appointment")
        verbose_name_plural = _("Appointments")
        indexes = [
            models.Index(fields=['status', 'appointment_date']),
            models.Index(fields=['service', 'appointment_date']),
            models.Index(fields=['created_at']),
        ]

    def clean(self):
        # Validate date is not in the past
        if self.appointment_date and self.appointment_date < timezone.localdate():
            raise ValidationError(
                {"appointment_date": _("Appointment date cannot be in the past.")}
            )

        # Validate time is within business hours (9:00 AM – 5:00 PM)
        if self.appointment_time:
            minutes = self.appointment_time.hour * 60 + self.appointment_time.minute
            if minutes < 9 * 60 or minutes > 17 * 60:
                raise ValidationError(
                    {"appointment_time": _("Appointment time must be between 09:00 AM and 05:00 PM.")}
                )

    def __str__(self):
        return f"{self.full_name} - {self.service.name}"


# ==========================
# Contact
# ==========================
class Contact(models.Model):
    name = models.CharField(_("Name"), max_length=150, db_index=True)
    email = models.EmailField(_("Email"), db_index=True)
    phone = models.CharField(_("Phone"), max_length=15, validators=[phone_validator], db_index=True)
    subject = models.CharField(_("Subject"), max_length=200)
    message = models.TextField(_("Message"))
    reply = models.TextField(_("Reply"), blank=True, null=True)
    replied = models.BooleanField(_("Replied"), default=False, db_index=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Contact")
        verbose_name_plural = _("Contacts")
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
    customer_name = models.CharField(_("Customer Name"), max_length=100, db_index=True)
    email = models.EmailField(_("Email"), blank=True, null=True, db_index=True)
    review = models.TextField(_("Review"))
    rating = models.PositiveSmallIntegerField(_("Rating"), default=5, db_index=True)
    approved = models.BooleanField(_("Approved"), default=True, db_index=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Review")
        verbose_name_plural = _("Reviews")
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
    CATEGORY = (
        ("General", _("General")),
        ("Government Scheme", _("Government Scheme")),
        ("Recruitment", _("Recruitment")),
        ("Scholarship", _("Scholarship")),
        ("Holiday", _("Holiday")),
        ("Notice", _("Notice")),
    )

    title = models.CharField(_("Title"), max_length=200, db_index=True)
    category = models.CharField(_("Category"), max_length=50, choices=CATEGORY, db_index=True)
    description = models.TextField(_("Description"))
    is_urgent = models.BooleanField(_("Urgent"), default=False, db_index=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Announcement")
        verbose_name_plural = _("Announcements")
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
    CATEGORY = (
        ("Cyber Cafe", _("Cyber Cafe")),
        ("Customers", _("Customers")),
        ("Certificates", _("Certificates")),
        ("Equipment", _("Equipment")),
        ("Office", _("Office")),
    )

    title = models.CharField(_("Title"), max_length=100)
    category = models.CharField(_("Category"), max_length=50, choices=CATEGORY, db_index=True)
    image = models.ImageField(_("Image"), upload_to="gallery/")

    class Meta:
        verbose_name = _("Gallery Image")
        verbose_name_plural = _("Gallery Images")
        indexes = [
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.title


# ==========================
# Service Charge
# ==========================
class ServiceCharge(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        verbose_name=_("Service"),
    )
    charge = models.DecimalField(_("Charge"), max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = _("Service Charge")
        verbose_name_plural = _("Service Charges")
        indexes = [
            models.Index(fields=['service']),
        ]

    def __str__(self):
        return f"{self.service.name} - ₹{self.charge}"


# ==========================
# Required Document
# ==========================
class RequiredDocument(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        verbose_name=_("Service"),
    )
    document_name = models.CharField(_("Document Name"), max_length=200, db_index=True)

    class Meta:
        verbose_name = _("Required Document")
        verbose_name_plural = _("Required Documents")
        indexes = [
            models.Index(fields=['service', 'document_name']),
        ]

    def __str__(self):
        return f"{self.service.name} - {self.document_name}"


# ==========================
# Download Form (PDF)
# ==========================
class DownloadForm(models.Model):
    title = models.CharField(_("Title"), max_length=200, db_index=True)
    category = models.CharField(_("Category"), max_length=100, db_index=True)
    pdf = models.FileField(_("PDF"), upload_to="forms/")
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Download Form")
        verbose_name_plural = _("Download Forms")
        indexes = [
            models.Index(fields=['category', 'uploaded_at']),
        ]

    def __str__(self):
        return self.title


# ==========================
# Government Scheme
# ==========================
class GovernmentScheme(models.Model):
    title = models.CharField(_("Title"), max_length=200, db_index=True)
    description = models.TextField(_("Description"))
    eligibility = models.TextField(_("Eligibility"), blank=True)
    last_date = models.DateField(_("Last Date"), null=True, blank=True, db_index=True)
    image = models.ImageField(_("Image"), upload_to="schemes/", blank=True, null=True)

    class Meta:
        verbose_name = _("Government Scheme")
        verbose_name_plural = _("Government Schemes")
        indexes = [
            models.Index(fields=['last_date']),
        ]

    def __str__(self):
        return self.title


# ==========================
# Job Notification
# ==========================
class JobNotification(models.Model):
    title = models.CharField(_("Title"), max_length=200, db_index=True)
    organization = models.CharField(_("Organization"), max_length=200, db_index=True)
    last_date = models.DateField(_("Last Date"), db_index=True)
    apply_link = models.URLField(_("Apply Link"), blank=True)
    description = models.TextField(_("Description"))
    icon = models.CharField(
        _("Icon"),
        max_length=50,
        default="briefcase",
        help_text=_("Font Awesome icon (e.g. 'fa-briefcase')"),
    )

    class Meta:
        verbose_name = _("Job Notification")
        verbose_name_plural = _("Job Notifications")
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
    question = models.CharField(_("Question"), max_length=300, db_index=True)
    answer = models.TextField(_("Answer"))

    class Meta:
        verbose_name = _("FAQ")
        verbose_name_plural = _("FAQs")
        indexes = [
            models.Index(fields=['question']),
        ]

    def __str__(self):
        return self.question


# ==========================
# Business Info (Singleton)
# ==========================
class BusinessInfo(models.Model):
    business_name = models.CharField(_("Business Name"), max_length=200)
    welcome_message = models.TextField(_("Welcome Message"))
    address = models.TextField(_("Address"))
    phone = models.CharField(_("Phone"), max_length=15, validators=[phone_validator])
    whatsapp = models.CharField(_("WhatsApp"), max_length=15, validators=[phone_validator])
    email = models.EmailField(_("Email"))
    google_map = models.TextField(
        _("Google Map"),
        help_text=_("Paste Google Maps Embed Code"),
    )
    business_hours = models.TextField(_("Business Hours"))
    registration_number = models.CharField(
        _("Registration Number"),
        max_length=100,
        blank=True,
        help_text=_("e.g. UDYAM-XX-00-0000000"),
    )
    certifications = models.TextField(
        _("Certifications / Authorizations"),
        blank=True,
        help_text=_("Enter each certification on a new line."),
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            existing = BusinessInfo.objects.first()
            if existing:
                self.pk = existing.pk
        super().save(*args, **kwargs)
        cache.delete('business_info')

    @classmethod
    def get_instance(cls):
        """Return the singleton BusinessInfo instance, creating one if it doesn't exist."""
        try:
            instance = cls.objects.first()
        except Exception:
            instance = None
        if not instance:
            instance = cls()
            instance.save()
        return instance

    class Meta:
        verbose_name = _("Business Information")
        verbose_name_plural = _("Business Information")


# corematoshree/models.py

class Application(models.Model):
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
        # ("razorpay", "Razorpay"),
        ("cash", "Cash"),
    )

    # --- Core fields ---
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("User"))
    service = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name=_("Service"))
    full_name = models.CharField(_("Full Name"), max_length=150, db_index=True)
    phone = models.CharField(_("Phone"), max_length=15, validators=[phone_validator], db_index=True)
    email = models.EmailField(_("Email"), db_index=True)
    address = models.TextField(_("Address"))
    extra_data = models.JSONField(_("Extra Data"), blank=True, null=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True, db_index=True)

    # --- Payment fields ---
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending",
        db_index=True
    )
    payment_transaction_id = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="upi",
        blank=True
    )
    payment_date = models.DateTimeField(null=True, blank=True)
    receipt_number = models.CharField(max_length=50, blank=True, null=True, unique=True)

    def generate_receipt_number(self):
        """Generate a unique receipt number e.g. RCP-2026-07-22-0001"""
        from django.utils import timezone
        now = timezone.now()
        return f"RCP-{now.strftime('%Y%m%d')}-{self.id:04d}"

    def __str__(self):
        return f"{self.full_name} – {self.service.name}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Application")
        verbose_name_plural = _("Applications")
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['service', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['payment_status']),
        ]


class DocumentUpload(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_name = models.CharField(_("Document Name"), max_length=200, db_index=True)
    file = models.FileField(_("File"), upload_to="applications/%Y/%m/%d/")
    is_mandatory = models.BooleanField(_("Mandatory"), default=True, db_index=True)
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True, db_index=True)
    verified = models.BooleanField(_("Verified by Admin"), default=False, db_index=True)

    class Meta:
        verbose_name = _("Document Upload")
        verbose_name_plural = _("Document Uploads")
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
    name = models.CharField(_("Name"), max_length=100, db_index=True)
    designation = models.CharField(_("Designation"), max_length=200)
    bio = models.TextField(_("Bio"), blank=True)
    photo = models.ImageField(_("Photo"), upload_to="team/", blank=True, null=True)
    order = models.PositiveIntegerField(_("Order"), default=0, help_text=_("Lower numbers appear first."))
    is_active = models.BooleanField(_("Active"), default=True, db_index=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = _("Team Member")
        verbose_name_plural = _("Team Members")
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return self.name


# ==========================
# Payment Setting (Singleton)
# ==========================
class PaymentSettings(models.Model):
    upi_id = models.CharField("UPI ID", max_length=100, blank=True, help_text="e.g. example@upi")
    upi_mobile = models.CharField("UPI Mobile", max_length=15, blank=True)
    qr_code = models.ImageField("QR Code", upload_to="payments/", blank=True, null=True)
    payment_instructions = models.TextField("Instructions", blank=True, default="Scan QR code and pay using any UPI app.")
    is_active = models.BooleanField("Active", default=True)

    def save(self, *args, **kwargs):
        # Enforce singleton: if this is a new record, reuse the existing one
        if not self.pk:
            existing = PaymentSettings.objects.first()
            if existing:
                self.pk = existing.pk
        # Ensure only one record is active at a time
        if self.is_active:
            PaymentSettings.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Payment Setting"
        verbose_name_plural = "Payment Settings"
