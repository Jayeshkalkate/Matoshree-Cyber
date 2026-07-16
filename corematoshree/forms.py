from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from .models import (
    User, Contact, Appointment, Review, Service, Announcement,
    JobNotification, GovernmentScheme, DownloadForm, ServiceCharge,
    Gallery, BusinessInfo, RequiredDocument   # <-- add this
)

# ==========================
# User Form
# ==========================
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        label=_("Email"),
        required=True
    )
    phone = forms.CharField(
        label=_("Phone"),
        max_length=15,
        required=False
    )
    address = forms.CharField(
        label=_("Address"),
        widget=forms.Textarea,
        required=False
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'address', 'password1', 'password2')
        labels = {
            'username': _('Username'),
            'password1': _('Password'),
            'password2': _('Confirm Password'),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'user'
        if commit:
            user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'address')
        labels = {
            'first_name': _('First Name'),
            'last_name': _('Last Name'),
            'email': _('Email'),
            'phone': _('Phone'),
            'address': _('Address'),
        }


# ==========================
# Contact Form (Public)
# ==========================
class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = [
            "name",
            "email",
            "phone",
            "subject",
            "message",
        ]
        labels = {
            'name': _('Name'),
            'email': _('Email'),
            'phone': _('Phone'),
            'subject': _('Subject'),
            'message': _('Message'),
        }
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": _("Your Name"),
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": _("Email Address"),
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": _("Phone Number"),
            }),
            "subject": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": _("Subject"),
            }),
            "message": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": _("Write your message..."),
            }),
        }


# ==========================
# Appointment Form (Public)
# ==========================
class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            "full_name",
            "phone",
            "email",
            "service",
            "appointment_date",
            "appointment_time",
            "message",
        ]
        labels = {
            'full_name': _('Full Name'),
            'phone': _('Phone'),
            'email': _('Email'),
            'service': _('Service'),
            'appointment_date': _('Appointment Date'),
            'appointment_time': _('Appointment Time'),
            'message': _('Additional Message'),
        }
        widgets = {
            "full_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": _("Full Name"),
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": _("Phone Number"),
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": _("Email Address"),
            }),
            "service": forms.Select(attrs={
                "class": "form-select",
            }),
            "appointment_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
            "appointment_time": forms.TimeInput(attrs={
                "class": "form-control",
                "type": "time",
            }),
            "message": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": _("Additional Message (Optional)"),
            }),
        }


# ==========================
# Review Form
# ==========================
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = [
            "customer_name",
            "email",
            "review",
            "rating",
        ]
        labels = {
            'customer_name': _('Your Name'),
            'email': _('Email Address'),
            'review': _('Review'),
            'rating': _('Rating'),
        }
        widgets = {
            "customer_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": _("Your Name"),
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": _("Email Address"),
            }),
            "review": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": _("Write your review..."),
            }),
            "rating": forms.NumberInput(attrs={
                "class": "form-control",
                "min": 1,
                "max": 5,
            }),
        }

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if rating < 1 or rating > 5:
            raise forms.ValidationError(_("Rating must be between 1 and 5."))
        return rating


# ------------------------------
# Dashboard ModelForms
# ------------------------------
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'category', 'description', 'active', 'icon', 'icon_color']
        widgets = {
            'icon_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control'}),
        }
        labels = {
            'name': _('Name'),
            'category': _('Category'),
            'description': _('Description'),
            'active': _('Active'),
            'icon': _('Icon'),
            'icon_color': _('Icon Color'),
        }


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'category', 'description']
        labels = {
            'title': _('Title'),
            'category': _('Category'),
            'description': _('Description'),
        }


class JobNotificationForm(forms.ModelForm):
    class Meta:
        model = JobNotification
        fields = ['title', 'organization', 'last_date', 'apply_link', 'description', 'icon']
        labels = {
            'title': _('Title'),
            'organization': _('Organization'),
            'last_date': _('Last Date'),
            'apply_link': _('Apply Link'),
            'description': _('Description'),
            'icon': _('Icon'),
        }


class GovernmentSchemeForm(forms.ModelForm):
    class Meta:
        model = GovernmentScheme
        fields = ['title', 'description', 'eligibility', 'last_date', 'image']
        labels = {
            'title': _('Title'),
            'description': _('Description'),
            'eligibility': _('Eligibility'),
            'last_date': _('Last Date'),
            'image': _('Image'),
        }


class AppointmentFormDashboard(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['full_name', 'phone', 'email', 'service', 'appointment_date', 'appointment_time', 'message', 'status']
        labels = {
            'full_name': _('Full Name'),
            'phone': _('Phone'),
            'email': _('Email'),
            'service': _('Service'),
            'appointment_date': _('Appointment Date'),
            'appointment_time': _('Appointment Time'),
            'message': _('Message'),
            'status': _('Status'),
        }


class ContactFormDashboard(forms.ModelForm):
    class Meta:
        model = Contact
        # Added 'reply' field as per Step 2.2
        fields = ['name', 'email', 'phone', 'subject', 'message', 'replied', 'reply']
        labels = {
            'name': _('Name'),
            'email': _('Email'),
            'phone': _('Phone'),
            'subject': _('Subject'),
            'message': _('Message'),
            'replied': _('Replied'),
            'reply': _('Reply'),      # new label
        }


class DownloadFormForm(forms.ModelForm):
    class Meta:
        model = DownloadForm
        fields = ['title', 'category', 'pdf']
        labels = {
            'title': _('Title'),
            'category': _('Category'),
            'pdf': _('PDF'),
        }


# ==========================
# Additional Dashboard Forms
# ==========================
class ServiceChargeForm(forms.ModelForm):
    class Meta:
        model = ServiceCharge
        fields = ['service', 'charge']
        labels = {
            'service': _('Service'),
            'charge': _('Charge'),
        }
        widgets = {
            'service': forms.Select(attrs={'class': 'form-select'}),
            'charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class GalleryForm(forms.ModelForm):
    class Meta:
        model = Gallery
        fields = ['title', 'category', 'image']
        labels = {
            'title': _('Title'),
            'category': _('Category'),
            'image': _('Image'),
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Image Title')}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }


class BusinessInfoForm(forms.ModelForm):
    class Meta:
        model = BusinessInfo
        fields = '__all__'
        labels = {
            'business_name': _('Business Name'),
            'logo': _('Logo'),
            'welcome_message': _('Welcome Message'),
            'address': _('Address'),
            'phone': _('Phone'),
            'whatsapp': _('WhatsApp'),
            'email': _('Email'),
            'google_map': _('Google Map'),
            'business_hours': _('Business Hours'),
        }
        widgets = {
            'business_name': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'welcome_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'whatsapp': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'google_map': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'business_hours': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        
from django import forms
from .models import Application, DocumentUpload

class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['full_name', 'phone', 'email', 'address']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Full Name')}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Phone Number')}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('Email Address')}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Address')}),
        }


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = DocumentUpload
        fields = ['document_name', 'file']
        widgets = {
            'document_name': forms.HiddenInput(),  # we will set it from the required doc
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            ext = file.name.split('.')[-1].lower()
            if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
               raise forms.ValidationError(_("Only PDF, JPG, JPEG, and PNG files are allowed."))
        return file
        

class RequiredDocumentForm(forms.ModelForm):
    class Meta:
        model = RequiredDocument
        fields = ['service', 'document_name']
        labels = {
            'service': _('Service'),
            'document_name': _('Document Name'),
        }
        widgets = {
            'service': forms.Select(attrs={'class': 'form-select'}),
            'document_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g. Aadhaar Card'),   # changed
                'help_text': _('Enter one document per entry.')  # not directly used; we'll add in template
            }),
        }