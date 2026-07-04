from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import (
    User, Contact, Appointment, Review, Service, Announcement,
    JobNotification, GovernmentScheme, DownloadForm, ServiceCharge,
    Gallery, BusinessInfo
)

# ==========================
# User Form
# ==========================
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'address', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'user'  # default role for registration
        if commit:
            user.save()
        return user

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'address')

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
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Your Name",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "Email Address",
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Phone Number",
            }),
            "subject": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Subject",
            }),
            "message": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Write your message...",
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
        widgets = {
            "full_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Full Name",
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Phone Number",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "Email Address",
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
                "placeholder": "Additional Message (Optional)",
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
        widgets = {
            "customer_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Your Name",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "Email Address",
            }),
            "review": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Write your review...",
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
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating

# ------------------------------
# Dashboard ModelForms
# ------------------------------
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'category', 'description', 'active', 'icon']

class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'category', 'description']

class JobNotificationForm(forms.ModelForm):
    class Meta:
        model = JobNotification
        fields = ['title', 'organization', 'last_date', 'apply_link', 'description', 'icon']   # added icon

class GovernmentSchemeForm(forms.ModelForm):
    class Meta:
        model = GovernmentScheme
        fields = ['title', 'description', 'eligibility', 'last_date', 'image']   # added image

class AppointmentFormDashboard(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['full_name', 'phone', 'email', 'service', 'appointment_date', 'appointment_time', 'message', 'status']

class ContactFormDashboard(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'email', 'phone', 'subject', 'message', 'replied']

class DownloadFormForm(forms.ModelForm):
    class Meta:
        model = DownloadForm
        fields = ['title', 'category', 'pdf']

# ==========================
# Additional Dashboard Forms (NEW)
# ==========================
class ServiceChargeForm(forms.ModelForm):
    class Meta:
        model = ServiceCharge
        fields = ['service', 'charge']
        widgets = {
            'service': forms.Select(attrs={'class': 'form-select'}),
            'charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class GalleryForm(forms.ModelForm):
    class Meta:
        model = Gallery
        fields = ['title', 'category', 'image']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Image Title'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }

class BusinessInfoForm(forms.ModelForm):
    class Meta:
        model = BusinessInfo
        fields = '__all__'
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

