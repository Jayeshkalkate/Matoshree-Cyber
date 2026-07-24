from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
import re

from .models import (
    User, Contact, Appointment, Review, Service, Announcement,
    JobNotification, GovernmentScheme, DownloadForm, ServiceCharge,
    Gallery, BusinessInfo, RequiredDocument, Application, DocumentUpload,
    TeamMember, PaymentSettings,
)


# ==========================
# User Forms (unchanged)
# ==========================
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(label=_("Email"), required=True)
    phone = forms.CharField(
        label=_("Phone"),
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    address = forms.CharField(
        label=_("Address"),
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        required=False,
    )

    class Meta:
        model = User
        fields = ("username", "email", "phone", "address", "password1", "password2")
        labels = {
            "username": _("Username"),
            "password1": _("Password"),
            "password2": _("Confirm Password"),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = "user"
        if commit:
            user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "address")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


# ==========================
# Public Forms (unchanged)
# ==========================
class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ("name", "email", "phone", "subject", "message")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Your Name")}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": _("Email Address")}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Phone Number")}),
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Subject")}),
            "message": forms.Textarea(
                attrs={"class": "form-control", "rows": 5, "placeholder": _("Write your message...")}
            ),
        }


class AppointmentForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        appointment_time = cleaned_data.get('appointment_time')
        if appointment_time:
            minutes = appointment_time.hour * 60 + appointment_time.minute
            if minutes < 9 * 60 or minutes > 17 * 60:
                raise forms.ValidationError(
                    _("Appointment time must be between 09:00 AM and 05:00 PM.")
                )
        return cleaned_data

    class Meta:
        model = Appointment
        fields = (
            "full_name", "phone", "email", "service",
            "appointment_date", "appointment_time", "message",
        )
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Full Name")}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Phone Number")}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": _("Email Address")}),
            "service": forms.Select(attrs={"class": "form-select"}),
            "appointment_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "appointment_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "message": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": _("Additional Message (Optional)")}
            ),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("customer_name", "email", "review", "rating")
        widgets = {
            "customer_name": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Your Name")}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": _("Email Address")}),
            "review": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": _("Write your review...")}
            ),
            "rating": forms.HiddenInput(),
        }

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is None or rating < 1 or rating > 5:
            raise forms.ValidationError(_("Rating must be between 1 and 5."))
        return rating


# ==========================
# Dashboard / Admin Forms (mostly unchanged)
# ==========================
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ("name", "category", "description", "active", "icon", "icon_color", "payment_required")
        widgets = {
            "icon_color": forms.TextInput(attrs={"type": "color", "class": "form-control"}),
        }


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ("title", "category", "description", "is_urgent")


class JobNotificationForm(forms.ModelForm):
    class Meta:
        model = JobNotification
        fields = ("title", "organization", "last_date", "apply_link", "description", "icon")


class GovernmentSchemeForm(forms.ModelForm):
    class Meta:
        model = GovernmentScheme
        fields = ("title", "description", "eligibility", "last_date", "image")


class AppointmentFormDashboard(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = (
            "full_name", "phone", "email", "service",
            "appointment_date", "appointment_time", "message", "status",
        )


class ContactFormDashboard(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ("name", "email", "phone", "subject", "message", "replied", "reply")


class DownloadFormForm(forms.ModelForm):
    class Meta:
        model = DownloadForm
        fields = ("title", "category", "pdf")


class ServiceChargeForm(forms.ModelForm):
    class Meta:
        model = ServiceCharge
        fields = ("service", "charge")
        widgets = {
            "service": forms.Select(attrs={"class": "form-select"}),
            "charge": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }


class GalleryForm(forms.ModelForm):
    class Meta:
        model = Gallery
        fields = ("title", "category", "image")
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Image Title")}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "image": forms.FileInput(attrs={"class": "form-control"}),
        }


class BusinessInfoForm(forms.ModelForm):
    class Meta:
        model = BusinessInfo
        fields = "__all__"
        widgets = {
            "business_name": forms.TextInput(attrs={"class": "form-control"}),
            "welcome_message": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "whatsapp": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "google_map": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "business_hours": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "registration_number": forms.TextInput(attrs={"class": "form-control"}),
            "certifications": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }


# ==========================
# Application & Document Forms (unchanged)
# ==========================
class ApplicationForm(forms.ModelForm):
    extra_data = forms.CharField(
        label=_("Additional Information"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": _("Any extra details (optional)")}),
        help_text=_("Provide any additional information relevant to your application.")
    )

    class Meta:
        model = Application
        fields = ("full_name", "phone", "email", "address", "extra_data")
        exclude = (
            'user', 'service', 'status',
            'payment_status', 'payment_method', 'payment_app',
            'utr_number', 'receipt_number', 'payment_date',
            'payment_transaction_id',
        )
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Full Name")}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Phone Number")}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": _("Email Address")}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": _("Address")}),
        }

    def clean_extra_data(self):
        data = self.cleaned_data.get('extra_data', '').strip()
        return {'details': data} if data else {}


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = DocumentUpload
        fields = ("document_name", "file")
        widgets = {
            "document_name": forms.HiddenInput(),
            "file": forms.FileInput(attrs={"class": "form-control"}),
        }

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            if file.size > 10 * 1024 * 1024:  # 10 MB
                raise forms.ValidationError(_("File size must be under 10 MB."))
            ext = file.name.split(".")[-1].lower()
            if ext not in ("pdf", "jpg", "jpeg", "png"):
                raise forms.ValidationError(_("Only PDF, JPG, JPEG, and PNG files are allowed."))
        else:
            raise forms.ValidationError(_("No file selected."))
        return file


class RequiredDocumentForm(forms.ModelForm):
    class Meta:
        model = RequiredDocument
        fields = ("service", "document_name")
        widgets = {
            "service": forms.Select(attrs={"class": "form-select"}),
            "document_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("e.g. PAN Card, Aadhar Card, Birth Certificate"),
                }
            ),
        }
        help_texts = {
            "document_name": _("Separate multiple documents with commas."),
        }


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = ('name', 'designation', 'bio', 'photo', 'order', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ==========================
# PAYMENT GATEWAY FORMS (ENHANCED)
# ==========================

class PaymentSettingsForm(forms.ModelForm):
    """
    Enhanced payment settings with support for multiple methods
    and proper validation.
    """
    class Meta:
        model = PaymentSettings
        fields = (
            'upi_id', 'upi_mobile', 'qr_code', 'payment_instructions',
            'is_active',
            # New fields for multi-gateway support (add these to your model)
            'razorpay_enabled', 'cash_enabled', 'upi_enabled',
            'test_mode', 'razorpay_test_key', 'razorpay_test_secret',
        )
        widgets = {
            'upi_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'example@upi'}),
            'upi_mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '9876543210'}),
            'qr_code': forms.FileInput(attrs={'class': 'form-control'}),
            'payment_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'razorpay_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'cash_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'upi_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'test_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'razorpay_test_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'rzp_test_...'}),
            'razorpay_test_secret': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '...'}),
        }

    def clean_upi_id(self):
        upi_id = self.cleaned_data.get('upi_id', '').strip()
        if upi_id:
            # Basic UPI ID format: something@something
            if not re.match(r'^[\w.-]+@[\w.-]+$', upi_id):
                raise forms.ValidationError(_("Enter a valid UPI ID (e.g., name@bank)"))
        return upi_id

    def clean(self):
        cleaned_data = super().clean()
        is_active = cleaned_data.get('is_active')
        upi_id = cleaned_data.get('upi_id')
        qr_code = cleaned_data.get('qr_code')
        razorpay_enabled = cleaned_data.get('razorpay_enabled')
        cash_enabled = cleaned_data.get('cash_enabled')
        upi_enabled = cleaned_data.get('upi_enabled')

        # If active, at least one payment method must be enabled
        if is_active:
            # Check if any method is available (consider both settings and actual data)
            has_upi = upi_enabled and (upi_id or qr_code)
            has_razorpay = razorpay_enabled
            has_cash = cash_enabled

            if not (has_upi or has_razorpay or has_cash):
                raise forms.ValidationError(
                    _("At least one payment method (UPI, Razorpay, or Cash) must be enabled "
                      "when payment settings are active.")
                )

            # If UPI is enabled, ensure either UPI ID or QR Code is provided
            if upi_enabled and not upi_id and not qr_code:
                raise forms.ValidationError(
                    _("UPI is enabled but neither UPI ID nor QR Code is provided.")
                )

            # Validate test keys if test mode is enabled
            if cleaned_data.get('test_mode'):
                if not cleaned_data.get('razorpay_test_key') or not cleaned_data.get('razorpay_test_secret'):
                    raise forms.ValidationError(
                        _("Test mode requires both Razorpay Test Key and Test Secret.")
                    )

        return cleaned_data


# Optional: Form for manual payment confirmation (used in templates)
class PaymentConfirmationForm(forms.Form):
    payment_app = forms.ChoiceField(
        label=_("Payment App"),
        choices=Application.PAYMENT_APP_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    utr_number = forms.CharField(
        label=_("UTR Number"),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("e.g. 123456789012")}),
        help_text=_("Optional but helps admin verify your payment."),
    )
    payment_method = forms.ChoiceField(
        label=_("Payment Method"),
        choices=Application.PAYMENT_METHOD_CHOICES,
        initial='upi',
        widget=forms.HiddenInput(),
    )
    
