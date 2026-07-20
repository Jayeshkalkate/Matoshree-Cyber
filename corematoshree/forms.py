from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import (
    User,
    Contact,
    Appointment,
    Review,
    Service,
    Announcement,
    JobNotification,
    GovernmentScheme,
    DownloadForm,
    ServiceCharge,
    Gallery,
    BusinessInfo,
    RequiredDocument,
    Application,
    DocumentUpload,
)


# ==========================
# User Forms
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
        labels = {
            "first_name": _("First Name"),
            "last_name": _("Last Name"),
            "email": _("Email"),
            "phone": _("Phone"),
            "address": _("Address"),
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


# ==========================
# Public Forms
# ==========================
class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ("name", "email", "phone", "subject", "message")
        labels = {
            "name": _("Name"),
            "email": _("Email"),
            "phone": _("Phone"),
            "subject": _("Subject"),
            "message": _("Message"),
        }
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
            # Convert to minutes since midnight
            minutes = appointment_time.hour * 60 + appointment_time.minute
            if minutes < 9 * 60 or minutes > 17 * 60:
                raise forms.ValidationError(
                    _("Appointment time must be between 09:00 AM and 05:00 PM.")
                )
        return cleaned_data

    class Meta:
        model = Appointment
        fields = (
            "full_name",
            "phone",
            "email",
            "service",
            "appointment_date",
            "appointment_time",
            "message",
        )
        labels = {
            "full_name": _("Full Name"),
            "phone": _("Phone"),
            "email": _("Email"),
            "service": _("Service"),
            "appointment_date": _("Appointment Date"),
            "appointment_time": _("Appointment Time"),
            "message": _("Additional Message"),
        }
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
        labels = {
            "customer_name": _("Your Name"),
            "email": _("Email Address"),
            "review": _("Review"),
            "rating": _("Rating"),
        }
        widgets = {
            "customer_name": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Your Name")}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": _("Email Address")}),
            "review": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": _("Write your review...")}
            ),
            # Rating is hidden because the template uses a custom star selector
            "rating": forms.HiddenInput(),
        }

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is None or rating < 1 or rating > 5:
            raise forms.ValidationError(_("Rating must be between 1 and 5."))
        return rating


# ==========================
# Dashboard / Admin Forms
# ==========================
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ("name", "category", "description", "active", "icon", "icon_color")
        labels = {
            "name": _("Name"),
            "category": _("Category"),
            "description": _("Description"),
            "active": _("Active"),
            "icon": _("Icon"),
            "icon_color": _("Icon Color"),
        }
        widgets = {
            "icon_color": forms.TextInput(attrs={"type": "color", "class": "form-control"}),
        }


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ("title", "category", "description", "is_urgent")
        labels = {
            "title": _("Title"),
            "category": _("Category"),
            "description": _("Description"),
            "is_urgent": _("Urgent"),
        }


class JobNotificationForm(forms.ModelForm):
    class Meta:
        model = JobNotification
        fields = ("title", "organization", "last_date", "apply_link", "description", "icon")
        labels = {
            "title": _("Title"),
            "organization": _("Organization"),
            "last_date": _("Last Date"),
            "apply_link": _("Apply Link"),
            "description": _("Description"),
            "icon": _("Icon"),
        }


class GovernmentSchemeForm(forms.ModelForm):
    class Meta:
        model = GovernmentScheme
        fields = ("title", "description", "eligibility", "last_date", "image")
        labels = {
            "title": _("Title"),
            "description": _("Description"),
            "eligibility": _("Eligibility"),
            "last_date": _("Last Date"),
            "image": _("Image"),
        }


class AppointmentFormDashboard(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = (
            "full_name",
            "phone",
            "email",
            "service",
            "appointment_date",
            "appointment_time",
            "message",
            "status",
        )
        labels = {
            "full_name": _("Full Name"),
            "phone": _("Phone"),
            "email": _("Email"),
            "service": _("Service"),
            "appointment_date": _("Appointment Date"),
            "appointment_time": _("Appointment Time"),
            "message": _("Message"),
            "status": _("Status"),
        }


class ContactFormDashboard(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ("name", "email", "phone", "subject", "message", "replied", "reply")
        labels = {
            "name": _("Name"),
            "email": _("Email"),
            "phone": _("Phone"),
            "subject": _("Subject"),
            "message": _("Message"),
            "replied": _("Replied"),
            "reply": _("Reply"),
        }


class DownloadFormForm(forms.ModelForm):
    class Meta:
        model = DownloadForm
        fields = ("title", "category", "pdf")
        labels = {
            "title": _("Title"),
            "category": _("Category"),
            "pdf": _("PDF"),
        }


class ServiceChargeForm(forms.ModelForm):
    class Meta:
        model = ServiceCharge
        fields = ("service", "charge")
        labels = {
            "service": _("Service"),
            "charge": _("Charge"),
        }
        widgets = {
            "service": forms.Select(attrs={"class": "form-select"}),
            "charge": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }


class GalleryForm(forms.ModelForm):
    class Meta:
        model = Gallery
        fields = ("title", "category", "image")
        labels = {
            "title": _("Title"),
            "category": _("Category"),
            "image": _("Image"),
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Image Title")}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "image": forms.FileInput(attrs={"class": "form-control"}),
        }


class BusinessInfoForm(forms.ModelForm):
    class Meta:
        model = BusinessInfo
        fields = "__all__"
        labels = {
            "business_name": _("Business Name"),
            "logo": _("Logo"),
            "welcome_message": _("Welcome Message"),
            "address": _("Address"),
            "phone": _("Phone"),
            "whatsapp": _("WhatsApp"),
            "email": _("Email"),
            "google_map": _("Google Map"),
            "business_hours": _("Business Hours"),
            "registration_number": _("Registration Number"),
            "certifications": _("Certifications / Authorizations"),
        }
        widgets = {
            "business_name": forms.TextInput(attrs={"class": "form-control"}),
            "logo": forms.FileInput(attrs={"class": "form-control"}),
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
# Application & Document Forms
# ==========================
class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ("full_name", "phone", "email", "address")
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Full Name")}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Phone Number")}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": _("Email Address")}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": _("Address")}),
        }


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
            # Validate file size (max 10MB)
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
        labels = {
            "service": _("Service"),
            "document_name": _("Document Names"),
        }
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
