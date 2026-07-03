from django import forms
from .models import Contact, Appointment, Review
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


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
# Contact Form
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
# Appointment Form
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
            "email",          # <-- NEW FIELD
            "review",
            "rating",
        ]

        widgets = {
            "customer_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Your Name",
            }),

            "email": forms.EmailInput(attrs={      # <-- NEW WIDGET
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
            raise forms.ValidationError(
                "Rating must be between 1 and 5."
            )

        return rating