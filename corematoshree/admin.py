from django.contrib import admin
from django.shortcuts import redirect
from django.contrib import messages
from .models import (
    Appointment,
    Contact,
    Review,
    Announcement,
    Gallery,
    Service,
    ServiceCharge,
    RequiredDocument,
    DownloadForm,
    GovernmentScheme,
    JobNotification,
    FAQ,
    BusinessInfo,
)
from django.contrib.auth.admin import UserAdmin
from .models import User

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import (
    Appointment, Contact, Review, Announcement, Gallery,
    Service, ServiceCharge, RequiredDocument, DownloadForm,
    GovernmentScheme, JobNotification, FAQ, BusinessInfo,
    User,  # custom User model
)


# ==========================
# Custom UserAdmin 
# ==========================

class CustomUserAdmin(UserAdmin):
    # The fields to be used in displaying the User model.
    # These override the definitions on the base UserAdmin
    # that reference specific fields on auth.User.
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone', 'address')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    filter_horizontal = ('groups', 'user_permissions',)

# Register the custom User model with the custom admin
admin.site.register(User, CustomUserAdmin)

# ==========================
# Appointment (with quick status updates)
# ==========================
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "phone",
        "service",
        "appointment_date",
        "appointment_time",
        "status",
    )
    list_filter = ("status", "appointment_date")
    search_fields = ("full_name", "phone", "email", "service")
    ordering = ("-appointment_date",)

    # ---- Inline editing for status ----
    list_editable = ("status",)   # Allows direct editing from the list view

    # ---- Custom batch actions ----
    actions = ["mark_as_confirmed", "mark_as_completed", "mark_as_cancelled"]

    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status="Confirmed")
        self.message_user(request, f"{updated} appointment(s) marked as Confirmed.")
    mark_as_confirmed.short_description = "Mark selected as Confirmed"

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status="Completed")
        self.message_user(request, f"{updated} appointment(s) marked as Completed.")
    mark_as_completed.short_description = "Mark selected as Completed"

    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status="Cancelled")
        self.message_user(request, f"{updated} appointment(s) marked as Cancelled.")
    mark_as_cancelled.short_description = "Mark selected as Cancelled"


# ==========================
# Contact
# ==========================
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "subject", "replied")
    list_filter = ("replied",)
    search_fields = ("name", "phone", "email", "subject")
    ordering = ("-created_at",)


# ==========================
# Review
# ==========================
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "rating", "approved")
    list_filter = ("rating", "approved")
    search_fields = ("customer_name",)


# ==========================
# Announcement
# ==========================
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "created_at")
    list_filter = ("category",)
    search_fields = ("title",)


# ==========================
# Gallery
# ==========================
@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ("title", "category")
    list_filter = ("category",)
    search_fields = ("title",)


# ==========================
# Services
# ==========================
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "active")
    list_filter = ("category", "active")
    search_fields = ("name", "category")


# ==========================
# Service Charges
# ==========================
@admin.register(ServiceCharge)
class ServiceChargeAdmin(admin.ModelAdmin):
    list_display = ("service", "charge")
    search_fields = ("service__name",)


# ==========================
# Required Documents
# ==========================
@admin.register(RequiredDocument)
class RequiredDocumentAdmin(admin.ModelAdmin):
    list_display = ("service", "document_name")
    search_fields = ("service__name", "document_name")


# ==========================
# Download Forms
# ==========================
@admin.register(DownloadForm)
class DownloadFormAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "uploaded_at")
    list_filter = ("category",)
    search_fields = ("title",)


# ==========================
# Government Schemes
# ==========================
@admin.register(GovernmentScheme)
class GovernmentSchemeAdmin(admin.ModelAdmin):
    list_display = ("title", "last_date")
    search_fields = ("title",)


# ==========================
# Job Notifications
# ==========================
@admin.register(JobNotification)
class JobNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "last_date")
    search_fields = ("title", "organization")


# ==========================
# FAQ
# ==========================
@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question",)
    search_fields = ("question",)


# ==========================
# Business Information
# ==========================
@admin.register(BusinessInfo)
class BusinessInfoAdmin(admin.ModelAdmin):
    list_display = ("business_name", "phone", "email")
    search_fields = ("business_name", "phone", "email")

