"""
Django Admin Configuration for the core application.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages

from .models import (
    User,
    Service,
    Appointment,
    Contact,
    Review,
    Announcement,
    Gallery,
    TeamMember,
    ServiceCharge,
    RequiredDocument,
    DownloadForm,
    GovernmentScheme,
    JobNotification,
    FAQ,
    BusinessInfo,
    Application,
    DocumentUpload,
)


# ==========================
# Custom User Admin
# ==========================
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    filter_horizontal = ('groups', 'user_permissions')

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


# ==========================
# Service Admin
# ==========================
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'active')
    list_filter = ('category', 'active')
    search_fields = ('name', 'category')
    ordering = ('name',)


# ==========================
# Appointment Admin
# ==========================
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'service', 'appointment_date', 'appointment_time', 'status')
    list_filter = ('status', 'appointment_date', 'service')
    search_fields = ('full_name', 'phone', 'email')
    ordering = ('-appointment_date',)
    list_editable = ('status',)   # Quick inline status updates
    actions = ['mark_as_confirmed', 'mark_as_completed', 'mark_as_cancelled']

    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='Confirmed')
        self.message_user(request, f"{updated} appointment(s) marked as Confirmed.", messages.SUCCESS)
    mark_as_confirmed.short_description = "Mark selected as Confirmed"

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='Completed')
        self.message_user(request, f"{updated} appointment(s) marked as Completed.", messages.SUCCESS)
    mark_as_completed.short_description = "Mark selected as Completed"

    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='Cancelled')
        self.message_user(request, f"{updated} appointment(s) marked as Cancelled.", messages.SUCCESS)
    mark_as_cancelled.short_description = "Mark selected as Cancelled"


# ==========================
# Contact Admin
# ==========================
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'subject', 'replied', 'created_at')
    list_filter = ('replied',)
    search_fields = ('name', 'phone', 'email', 'subject')
    ordering = ('-created_at',)
    actions = ['mark_as_replied']

    def mark_as_replied(self, request, queryset):
        updated = queryset.update(replied=True)
        self.message_user(request, f"{updated} contact(s) marked as replied.", messages.SUCCESS)
    mark_as_replied.short_description = "Mark selected as Replied"


# ==========================
# Review Admin
# ==========================
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'rating', 'approved', 'created_at')
    list_filter = ('rating', 'approved')
    search_fields = ('customer_name', 'email')
    ordering = ('-created_at',)
    actions = ['approve_reviews']

    def approve_reviews(self, request, queryset):
        updated = queryset.update(approved=True)
        self.message_user(request, f"{updated} review(s) approved.", messages.SUCCESS)
    approve_reviews.short_description = "Approve selected reviews"


# ==========================
# Announcement Admin
# ==========================
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_at')
    list_filter = ('category',)
    search_fields = ('title',)
    ordering = ('-created_at',)


# ==========================
# Gallery Admin
# ==========================
@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ('title', 'category')
    list_filter = ('category',)
    search_fields = ('title',)


# ==========================
# Service Charge Admin
# ==========================
@admin.register(ServiceCharge)
class ServiceChargeAdmin(admin.ModelAdmin):
    list_display = ('service', 'charge')
    search_fields = ('service__name',)
    ordering = ('service__name',)


# ==========================
# Required Document Admin
# ==========================
@admin.register(RequiredDocument)
class RequiredDocumentAdmin(admin.ModelAdmin):
    list_display = ('service', 'document_name')
    search_fields = ('service__name', 'document_name')
    ordering = ('service__name', 'document_name')


# ==========================
# Download Form Admin
# ==========================
@admin.register(DownloadForm)
class DownloadFormAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'uploaded_at')
    list_filter = ('category',)
    search_fields = ('title',)
    ordering = ('-uploaded_at',)


# ==========================
# Government Scheme Admin
# ==========================
@admin.register(GovernmentScheme)
class GovernmentSchemeAdmin(admin.ModelAdmin):
    list_display = ('title', 'last_date')
    search_fields = ('title',)
    ordering = ('-last_date',)


# ==========================
# Job Notification Admin
# ==========================
@admin.register(JobNotification)
class JobNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'last_date')
    search_fields = ('title', 'organization')
    ordering = ('last_date',)


# ==========================
# FAQ Admin
# ==========================
@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question',)
    search_fields = ('question',)


# ==========================
# Business Info Admin (Singleton)
# ==========================
@admin.register(BusinessInfo)
class BusinessInfoAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'phone', 'email', 'registration_number')
    fieldsets = (
        (None, {
            'fields': (
                'business_name', 'logo', 'welcome_message',
                'address', 'phone', 'whatsapp', 'email',
                'google_map', 'business_hours',
                'registration_number', 'certifications'
            )
        }),
    )


# ==========================
# Application & Document Upload (Inline)
# ==========================
class DocumentUploadInline(admin.TabularInline):
    model = DocumentUpload
    extra = 0
    readonly_fields = ('uploaded_at',)
    fields = ('document_name', 'file', 'is_mandatory', 'verified', 'uploaded_at')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'service', 'status', 'created_at')
    list_filter = ('status', 'service', 'created_at')
    search_fields = ('full_name', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [DocumentUploadInline]
    fieldsets = (
        (None, {'fields': ('user', 'service', 'full_name', 'phone', 'email', 'address', 'extra_data')}),
        ('Status', {'fields': ('status',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    ordering = ('-created_at',)

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'designation')
    ordering = ('order', 'name')
    list_editable = ('order', 'is_active')