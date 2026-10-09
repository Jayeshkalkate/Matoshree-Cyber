# =============================================================================
# IMPORTS
# =============================================================================

# ---- Standard Library ----
import os
import json
import hmac
import logging
import tempfile
from decimal import Decimal
from datetime import timedelta
from io import BytesIO
from datetime import datetime
import re
from .scraper import fetch_all_external_jobs
from urllib.parse import quote
from .scraper import fetch_all_external_schemes

# ---- Third-Party Libraries ----
import razorpay
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from pypdf import PdfReader, PdfWriter

# ---- Django Core ----
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView,
    PasswordResetCompleteView, PasswordChangeView, PasswordChangeDoneView
)
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.files.storage import default_storage
from django.core.files import File
from django.db import models, transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncWeek
from django.forms import formset_factory
from django.http import FileResponse, Http404, JsonResponse, HttpResponse
from django.utils.text import slugify
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# ---- Local Application ----
from .models import (
    User, Appointment, Review, Service, Announcement, JobNotification,
    GovernmentScheme, DownloadForm, ServiceCharge, Gallery, BusinessInfo,
    RequiredDocument, FAQ, Application, DocumentUpload, Contact, TeamMember,
    PaymentSettings, PaymentLog, ApplicationStatusHistory, Notification, AuditLog,
)
from .forms import (
    TeamMemberForm, CustomUserCreationForm, ProfileUpdateForm, ContactForm,
    AppointmentForm, ReviewForm, ServiceForm, AnnouncementForm,
    JobNotificationForm, GovernmentSchemeForm, AppointmentFormDashboard,
    ContactFormDashboard, DownloadFormForm, ServiceChargeForm, GalleryForm,
    BusinessInfoForm, RequiredDocumentForm, ApplicationForm, DocumentUploadForm,
    PaymentSettingsForm,
)
from .utils import (
    get_business, get_payment_settings, is_admin, is_superadmin,
    fetch_external_jobs, compute_payment_breakdown
)

# ---- Logger ----
logger = logging.getLogger(__name__)


def get_service_charge(service):
    """Return the current service charge without relying on arbitrary FK ordering."""
    return service.servicecharge_set.order_by('id').first()


def _client_ip(request):
    from .security import client_ip
    ip = client_ip(request)
    return None if ip == 'unknown' else ip


def audit(request, action, obj=None, details=None):
    try:
        AuditLog.objects.create(
            actor=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
            action=action,
            model_name=obj.__class__.__name__ if obj is not None else '',
            object_id=str(getattr(obj, 'pk', '')) if obj is not None else '',
            details=details or {},
            ip_address=_client_ip(request),
        )
    except Exception:
        logger.exception('Unable to write audit log')


def notify_user(user, title, message, application=None):
    try:
        Notification.objects.create(user=user, application=application, title=title, message=message)
    except Exception:
        logger.exception('Unable to create notification')


def send_platform_email(subject, message, recipient_list):
    """Send email through a free HTTP provider when configured; fall back to Django email."""
    provider = getattr(settings, 'EMAIL_PROVIDER', 'console').lower()
    recipients = [r for r in recipient_list if r]
    if not recipients:
        return False
    try:
        if provider == 'brevo' and getattr(settings, 'BREVO_API_KEY', ''):
            import requests
            response = requests.post(
                'https://api.brevo.com/v3/smtp/email',
                headers={'api-key': settings.BREVO_API_KEY, 'accept': 'application/json', 'content-type': 'application/json'},
                json={'sender': {'email': settings.DEFAULT_FROM_EMAIL}, 'to': [{'email': r} for r in recipients], 'subject': subject, 'textContent': message},
                timeout=15,
            )
            response.raise_for_status()
            return True
        if provider == 'resend' and getattr(settings, 'RESEND_API_KEY', ''):
            import requests
            response = requests.post(
                'https://api.resend.com/emails',
                headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}', 'Content-Type': 'application/json'},
                json={'from': settings.DEFAULT_FROM_EMAIL, 'to': recipients, 'subject': subject, 'text': message},
                timeout=15,
            )
            response.raise_for_status()
            return True
        if provider == 'console':
            logger.info('EMAIL [%s] to %s\n%s', subject, ', '.join(recipients), message)
            return True
        if provider in ('brevo', 'resend'):
            logger.warning('EMAIL_PROVIDER=%s is configured but its API key is missing.', provider)
            return False
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
        return True
    except Exception:
        logger.exception('Email delivery failed')
        return False


# =============================================================================
# ERRORS 404 and 500
# =============================================================================
def custom_404(request, exception):
    """Custom 404 error page."""
    return render(request, '404.html', {
        'business': get_business(),
    }, status=404)

def custom_403(request, exception=None):
    return render(request, '403.html', {'business': get_business()}, status=403)


def custom_500(request):
    """Custom 500 error page."""
    return render(request, '500.html', {
        'business': get_business(),
    }, status=500)


# =============================================================================
# ROBOTS.TXT
# =============================================================================
def robots_txt(request):
    """Allow public pages, keep private/transactional/admin areas out of search."""
    private = [
        "/admin/", "/admin-dashboard/", "/superadmin-dashboard/", "/dashboard-section/",
        "/reports/", "/profile/", "/my-applications/", "/application/", "/application-admin/",
        "/application-ajax/", "/notifications/", "/payment-checkout/", "/payment-success/",
        "/payment-failure/", "/create-razorpay-order/", "/razorpay-webhook/", "/download-receipt/",
        "/document/", "/split-pdf/", "/mark-payment-done/", "/login/", "/register/", "/logout/",
        "/auth/", "/password-", "/track-application/", "/apply/",
    ]
    lines = ["User-agent: *"] + [f"Disallow: {p}" for p in private] + [
        "Allow: /",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


# =============================================================================
# HELPERS (with caching)
# =============================================================================

def send_admin_notification(subject, message, recipient_list=None):
    """Send email to admin(s) with error handling."""
    if recipient_list is None:
        recipient_list = [getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL)]
    try:
        send_platform_email(subject, message, recipient_list)
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")


def send_welcome_email(user):
    """Send welcome email to new user."""
    try:
        send_platform_email("Welcome to our platform", (f"Hi {user.username},\n\n" "Thank you for registering. You can now book appointments and apply for services.\n" "Visit our website to get started."), [user.email])
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")


def send_payment_confirmation(application):
    """Send payment confirmation email to user and admin."""
    try:
        charge = get_service_charge(application.service)
        amount = application.total_paid or (charge.charge if charge else 0)
        business_name = get_business().business_name if get_business() else 'Matoshree Cyber Center'

        send_mail(
            subject=f"Payment Confirmed - Application #{application.id}",
            message=(
                f"Dear {application.full_name},\n\n"
                f"Your payment for {application.service.name} has been confirmed.\n"
                f"Receipt No: {application.receipt_number}\n"
                f"Amount Paid: ₹{amount}\n\n"
                f"Thank you for choosing our services.\n\n"
                f"Regards,\n{business_name}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.email],
            fail_silently=True,
        )
        # Admin notification
        send_admin_notification(
            subject=f"Payment Received - {application.full_name}",
            message=f"Payment of ₹{amount} received for {application.service.name}.\nReceipt: {application.receipt_number}"
        )
    except Exception as e:
        logger.error(f"Failed to send payment confirmation email: {e}")


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            audit(request, 'registration_success', user, {'method': 'password'})
            messages.success(request, "Account created successfully!")
            send_welcome_email(user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {
        'form': form,
        'business': get_business(),
    })


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            audit(request, 'profile_updated', request.user, {'fields': sorted(form.changed_data)})
            messages.success(request, "Profile updated successfully!")
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, 'profile.html', {
        'form': form,
        'business': get_business(),
        'google_linked': request.user.social_identities.filter(provider='google').exists(),
    })


# -----------------------------------------------------------------------------
# Password Reset Views
# -----------------------------------------------------------------------------
class CustomPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        subject = render_to_string(subject_template_name, context).strip().replace('\n', ' ')
        body = render_to_string(email_template_name, context)
        send_platform_email(subject, body, [to_email])


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'registration/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'registration/password_reset_complete.html'


# -----------------------------------------------------------------------------
# Password Change Views
# -----------------------------------------------------------------------------
class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'password_change.html'
    success_url = reverse_lazy('password_change_done')


class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = 'password_change_done.html'


# =============================================================================
# DASHBOARD (ADMIN & SUPERADMIN)
# =============================================================================

DASHBOARD_CACHE_KEY = 'dashboard_data_v2'
DASHBOARD_CACHE_TTL = 120

def _get_dashboard_common_data():
    cache_key = DASHBOARD_CACHE_KEY
    cached = cache.get(cache_key)
    if cached is not None:
        data = cached
    else:
        # Build serializable data (lists of dicts) - safe for cache
        data = {
            'services': list(Service.objects.values('id', 'name', 'category', 'active', 'icon', 'icon_color')),
            'appointments': list(Appointment.objects.select_related('service').values(
                'id', 'full_name', 'phone', 'email', 'service__name',
                'appointment_date', 'appointment_time', 'status', 'created_at'
            ).order_by('-appointment_date')[:100]),
            'contacts': list(Contact.objects.values('id', 'name', 'email', 'phone', 'subject', 'message', 'reply', 'replied', 'created_at')[:100]),
            'announcements': list(Announcement.objects.values('id', 'title', 'category', 'description', 'created_at')[:100]),
            'jobs': list(JobNotification.objects.values('id', 'title', 'organization', 'last_date', 'apply_link', 'description', 'icon')[:100]),
            'schemes': list(GovernmentScheme.objects.values('id', 'title', 'description', 'eligibility', 'last_date', 'image')[:100]),
            'forms_list': list(DownloadForm.objects.values('id', 'title', 'category', 'pdf', 'uploaded_at')[:100]),
            'servicecharges': list(ServiceCharge.objects.select_related('service').values('id', 'service__name', 'charge')),
            'gallery_images': list(Gallery.objects.values('id', 'title', 'category', 'image')[:100]),
            'business_info': BusinessInfo.objects.first(),
            'applications': list(Application.objects.select_related('user', 'service').values(
                'id', 'application_number', 'user__username', 'service__name', 'full_name', 'phone',
                'email', 'address', 'status', 'payment_status', 'created_at'
            ).order_by('-created_at')[:100]),
            'required_docs': list(RequiredDocument.objects.select_related('service').values(
                'id', 'service__name', 'document_name'
            ).order_by('service__name')),
            'team_members': list(TeamMember.objects.values('id', 'name', 'designation', 'bio', 'photo', 'order', 'is_active')),
        }
        cache.set(cache_key, data, DASHBOARD_CACHE_TTL)

    # Add forms (not cached)
    payment_settings_instance = PaymentSettings.objects.filter(is_active=True).first()
    if not payment_settings_instance:
        payment_settings_instance = PaymentSettings.objects.first()
        if not payment_settings_instance:
            payment_settings_instance = PaymentSettings.objects.create(is_active=False)

    data.update({
        'service_form': ServiceForm(),
        'announcement_form': AnnouncementForm(),
        'job_form': JobNotificationForm(),
        'scheme_form': GovernmentSchemeForm(),
        'appointment_form': AppointmentFormDashboard(),
        'contact_form': ContactFormDashboard(),
        'download_form': DownloadFormForm(),
        'servicecharge_form': ServiceChargeForm(),
        'gallery_form': GalleryForm(),
        'businessinfo_form': BusinessInfoForm(instance=BusinessInfo.objects.first()),
        'required_doc_form': RequiredDocumentForm(),
        'team_member_form': TeamMemberForm(),
        'payment_settings_form': PaymentSettingsForm(instance=payment_settings_instance),
        'payment_settings': payment_settings_instance,
    })
    return data


# -----------------------------------------------------------------------------
# Dashboard POST helpers
# -----------------------------------------------------------------------------

def _clear_section_cache(section):
    cache.delete(f'dashboard_section_{section}')

def _clear_all_section_caches():
    sections = [
        'services', 'appointments', 'contacts', 'announcements', 'jobs',
        'schemes', 'forms', 'servicecharges', 'gallery', 'requireddocs',
        'applications', 'users'
    ]
    for section in sections:
        cache.delete(f'dashboard_section_{section}')

def _handle_add(model_type, request, is_super):
    if model_type == 'service':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Service added.")
            _clear_section_cache('services')
        else:
            messages.error(request, "Error adding service.")
    elif model_type == 'requireddoc':
        raw_docs = request.POST.get('document_name', '').strip()
        service_id = request.POST.get('service')
        if not service_id:
            messages.error(request, "Please select a service.")
            return
        doc_names = [name.strip() for name in raw_docs.split(',') if name.strip()]
        if not doc_names:
            messages.error(request, "Please enter at least one document name.")
            return
        service = get_object_or_404(Service, id=service_id)
        created = 0
        for doc_name in doc_names:
            doc_obj, created_flag = RequiredDocument.objects.get_or_create(
                service=service, document_name=doc_name
            )
            if created_flag:
                created += 1
        messages.success(request, f"{created} document(s) added for “{service.name}”.")
        _clear_section_cache('requireddocs')
    elif model_type == 'teammember':
        form = TeamMemberForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Team member added.")
            _clear_section_cache('teammembers')
        else:
            messages.error(request, "Error adding team member.")
    elif model_type == 'announcement':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Announcement added.")
            _clear_section_cache('announcements')
        else:
            messages.error(request, "Error adding announcement.")
    elif model_type == 'job':
        form = JobNotificationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Job notification added.")
            _clear_section_cache('jobs')
        else:
            messages.error(request, "Error adding job.")
    elif model_type == 'scheme':
        form = GovernmentSchemeForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Scheme added.")
            _clear_section_cache('schemes')
        else:
            messages.error(request, "Error adding scheme.")
    elif model_type == 'appointment':
        form = AppointmentFormDashboard(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Appointment added.")
            _clear_section_cache('appointments')
        else:
            messages.error(request, "Error adding appointment.")
    elif model_type == 'contact':
        form = ContactFormDashboard(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Contact added.")
            _clear_section_cache('contacts')
        else:
            messages.error(request, "Error adding contact.")
    elif model_type == 'form':
        form = DownloadFormForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Download form uploaded.")
            _clear_section_cache('forms')
        else:
            messages.error(request, "Error uploading form.")
    elif model_type == 'servicecharge':
        form = ServiceChargeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Service charge added.")
            _clear_section_cache('servicecharges')
        else:
            messages.error(request, "Error adding service charge.")
    elif model_type == 'gallery':
        form = GalleryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Gallery image uploaded.")
            _clear_section_cache('gallery')
        else:
            messages.error(request, "Error uploading gallery image.")
    else:
        messages.error(request, "Unknown model type for add.")


def _handle_edit(model_type, obj_id, request):
    if model_type == 'service':
        instance = get_object_or_404(Service, id=obj_id)
        form = ServiceForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Service updated.")
            _clear_section_cache('services')
        else:
            messages.error(request, "Error updating service.")
    elif model_type == 'requireddoc':
        instance = get_object_or_404(RequiredDocument, id=obj_id)
        form = RequiredDocumentForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Required document updated.")
            _clear_section_cache('requireddocs')
        else:
            messages.error(request, "Error updating required document.")
    elif model_type == 'teammember':
        instance = get_object_or_404(TeamMember, id=obj_id)
        form = TeamMemberForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Team member updated.")
            _clear_section_cache('teammembers')
        else:
            messages.error(request, "Error updating team member.")
    elif model_type == 'announcement':
        instance = get_object_or_404(Announcement, id=obj_id)
        form = AnnouncementForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Announcement updated.")
            _clear_section_cache('announcements')
        else:
            messages.error(request, "Error updating announcement.")
    elif model_type == 'job':
        instance = get_object_or_404(JobNotification, id=obj_id)
        form = JobNotificationForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Job updated.")
            _clear_section_cache('jobs')
        else:
            messages.error(request, "Error updating job.")
    elif model_type == 'scheme':
        instance = get_object_or_404(GovernmentScheme, id=obj_id)
        form = GovernmentSchemeForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Scheme updated.")
            _clear_section_cache('schemes')
        else:
            messages.error(request, "Error updating scheme.")
    elif model_type == 'appointment':
        instance = get_object_or_404(Appointment, id=obj_id)
        form = AppointmentFormDashboard(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Appointment updated.")
            _clear_section_cache('appointments')
        else:
            messages.error(request, "Error updating appointment.")
    elif model_type == 'contact':
        instance = get_object_or_404(Contact, id=obj_id)
        form = ContactFormDashboard(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Contact updated.")
            _clear_section_cache('contacts')
        else:
            messages.error(request, "Error updating contact.")
    elif model_type == 'form':
        instance = get_object_or_404(DownloadForm, id=obj_id)
        form = DownloadFormForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Form updated.")
            _clear_section_cache('forms')
        else:
            messages.error(request, "Error updating form.")
    elif model_type == 'servicecharge':
        instance = get_object_or_404(ServiceCharge, id=obj_id)
        form = ServiceChargeForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Service charge updated.")
            _clear_section_cache('servicecharges')
        else:
            messages.error(request, "Error updating service charge.")
    elif model_type == 'gallery':
        instance = get_object_or_404(Gallery, id=obj_id)
        form = GalleryForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Gallery image updated.")
            _clear_section_cache('gallery')
        else:
            messages.error(request, "Error updating gallery image.")
    elif model_type == 'businessinfo':
        if not obj_id:
            instance = BusinessInfo.objects.first()
            if not instance:
                instance = BusinessInfo()
        else:
            instance = get_object_or_404(BusinessInfo, id=obj_id)
        form = BusinessInfoForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Business info updated.")
            cache.delete('business_info')
            _clear_all_section_caches()
        else:
            messages.error(request, "Error updating business info.")


def _handle_delete(model_type, obj_id, request):
    if model_type == 'service':
        get_object_or_404(Service, id=obj_id).delete()
        messages.success(request, "Service deleted.")
        _clear_section_cache('services')
    elif model_type == 'announcement':
        get_object_or_404(Announcement, id=obj_id).delete()
        messages.success(request, "Announcement deleted.")
        _clear_section_cache('announcements')
    elif model_type == 'teammember':
        get_object_or_404(TeamMember, id=obj_id).delete()
        messages.success(request, "Team member deleted.")
        _clear_section_cache('teammembers')
    elif model_type == 'requireddoc':
        get_object_or_404(RequiredDocument, id=obj_id).delete()
        messages.success(request, "Required document deleted.")
        _clear_section_cache('requireddocs')
    elif model_type == 'job':
        get_object_or_404(JobNotification, id=obj_id).delete()
        messages.success(request, "Job deleted.")
        _clear_section_cache('jobs')
    elif model_type == 'scheme':
        get_object_or_404(GovernmentScheme, id=obj_id).delete()
        messages.success(request, "Scheme deleted.")
        _clear_section_cache('schemes')
    elif model_type == 'appointment':
        get_object_or_404(Appointment, id=obj_id).delete()
        messages.success(request, "Appointment deleted.")
        _clear_section_cache('appointments')
    elif model_type == 'contact':
        get_object_or_404(Contact, id=obj_id).delete()
        messages.success(request, "Contact deleted.")
        _clear_section_cache('contacts')
    elif model_type == 'form':
        get_object_or_404(DownloadForm, id=obj_id).delete()
        messages.success(request, "Form deleted.")
        _clear_section_cache('forms')
    elif model_type == 'servicecharge':
        get_object_or_404(ServiceCharge, id=obj_id).delete()
        messages.success(request, "Service charge deleted.")
        _clear_section_cache('servicecharges')
    elif model_type == 'gallery':
        get_object_or_404(Gallery, id=obj_id).delete()
        messages.success(request, "Gallery image deleted.")
        _clear_section_cache('gallery')
    else:
        messages.error(request, "Unknown model type for delete.")


def _handle_payment_settings(request):
    instance = PaymentSettings.objects.first() or PaymentSettings()
    form = PaymentSettingsForm(request.POST, request.FILES, instance=instance)
    if form.is_valid():
        payment_settings = form.save(commit=False)
        payment_settings.save()
        messages.success(request, "Payment settings updated.")
        cache.delete('payment_settings')
    else:
        logger.error(f"PaymentSettings form errors: {form.errors.as_json()}")
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        messages.error(request, "Please correct the errors below.")
    cache.delete(DASHBOARD_CACHE_KEY)
    _clear_all_section_caches()


def _handle_user_role_edit(request):
    user_id = request.POST.get('user_id')
    new_role = request.POST.get('new_role')
    if user_id and new_role:
        if new_role not in dict(User.ROLE_CHOICES):
            messages.error(request, 'Invalid role.')
            return
        user = get_object_or_404(User, id=user_id)
        old_role = user.role
        if user == request.user and new_role != 'superadmin':
            messages.error(request, 'You cannot remove your own superadmin role from this screen.')
            return
        user.role = new_role
        user.save(update_fields=['role'])
        audit(request, 'user_role_changed', user, {'old_role': old_role, 'new_role': new_role})
        messages.success(request, "User role updated.")
    cache.delete(DASHBOARD_CACHE_KEY)
    _clear_section_cache('users')


# -----------------------------------------------------------------------------
# Main dashboard POST dispatcher
# -----------------------------------------------------------------------------

def _handle_dashboard_post(request, is_super=False):
    action = request.POST.get('action')
    model_type = request.POST.get('model_type')
    obj_id = request.POST.get('id')

    if action == 'add':
        _handle_add(model_type, request, is_super)
        cache.delete(DASHBOARD_CACHE_KEY)
        return redirect('superadmin_dashboard' if is_super else 'admin_dashboard')

    elif model_type == 'paymentsettings':
        _handle_payment_settings(request)
        return redirect('superadmin_dashboard' if is_super else 'admin_dashboard')

    elif action == 'edit':
        _handle_edit(model_type, obj_id, request)
        cache.delete(DASHBOARD_CACHE_KEY)
        if model_type == 'businessinfo':
            cache.delete('business_info')
        return redirect('superadmin_dashboard' if is_super else 'admin_dashboard')

    elif action == 'delete':
        _handle_delete(model_type, obj_id, request)
        cache.delete(DASHBOARD_CACHE_KEY)
        return redirect('superadmin_dashboard' if is_super else 'admin_dashboard')

    elif is_super and action == 'edit_user':
        _handle_user_role_edit(request)
        return redirect('superadmin_dashboard')

    return None


# -----------------------------------------------------------------------------
# Dashboard views
# -----------------------------------------------------------------------------

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    context = _get_dashboard_common_data()
    if request.method == 'POST':
        response = _handle_dashboard_post(request, is_super=False)
        if response:
            return response
    context['business'] = get_business()
    return render(request, 'dashboard.html', context)


@login_required
@user_passes_test(is_superadmin)
def superadmin_dashboard(request):
    context = _get_dashboard_common_data()
    context['users'] = User.objects.all().order_by('username').only('id', 'username', 'email', 'role', 'is_staff')
    if request.method == 'POST':
        response = _handle_dashboard_post(request, is_super=True)
        if response:
            return response
    context['business'] = get_business()
    return render(request, 'dashboard.html', context)


SECTION_CACHE_TTL = 300

@login_required
@user_passes_test(is_admin)
def dashboard_section_data(request, section):
    cache_key = f'dashboard_section_{section}'
    data = cache.get(cache_key)
    if data is None:
        if section == 'services':
            data = {'services': list(Service.objects.values('id', 'name', 'category', 'active', 'icon', 'icon_color'))}
        elif section == 'appointments':
            data = {'appointments': list(Appointment.objects.select_related('service').values(
                'id', 'full_name', 'phone', 'email', 'service__name',
                'appointment_date', 'appointment_time', 'status', 'created_at'
            ).order_by('-appointment_date'))}
        elif section == 'contacts':
            data = {'contacts': list(Contact.objects.values('id', 'name', 'email', 'phone', 'subject', 'message', 'reply', 'replied', 'created_at'))}
        elif section == 'announcements':
            data = {'announcements': list(Announcement.objects.values('id', 'title', 'category', 'description', 'created_at'))}
        elif section == 'jobs':
            data = {'jobs': list(JobNotification.objects.values('id', 'title', 'organization', 'last_date', 'apply_link', 'description', 'icon'))}
        elif section == 'schemes':
            data = {'schemes': list(GovernmentScheme.objects.values('id', 'title', 'description', 'eligibility', 'last_date', 'image'))}
        elif section == 'forms':
            data = {'forms': list(DownloadForm.objects.values('id', 'title', 'category', 'pdf', 'uploaded_at'))}
        elif section == 'servicecharges':
            data = {'servicecharges': list(ServiceCharge.objects.select_related('service').values(
                'id', 'service__name', 'charge'))}
        elif section == 'gallery':
            data = {'gallery': list(Gallery.objects.values('id', 'title', 'category', 'image'))}
        elif section == 'requireddocs':
            data = {'requireddocs': list(RequiredDocument.objects.select_related('service').values(
                'id', 'service__name', 'document_name'))}
        elif section == 'applications':
            data = {'applications': list(Application.objects.select_related('user', 'service').values(
                'id', 'application_number', 'user__username', 'service__name', 'full_name', 'phone',
                'email', 'address', 'status', 'payment_status', 'created_at'
            ).order_by('-created_at'))}
        elif section == 'users' and is_superadmin(request.user):
            data = {'users': list(User.objects.values('id', 'username', 'email', 'role', 'is_staff'))}
        else:
            data = {'error': 'Invalid section.'}
        cache.set(cache_key, data, SECTION_CACHE_TTL)
    return JsonResponse(data)


# =============================================================================
# PUBLIC VIEWS
# =============================================================================

def home(request):
    all_gallery = Gallery.objects.all().order_by('-id')
    valid_gallery = [
        img for img in all_gallery
        if img.image and default_storage.exists(img.image.name)
    ]
    context = {
        'business': get_business(),
        'services': Service.objects.filter(active=True)[:8].only('name', 'description', 'icon', 'icon_color'),
        'announcements': Announcement.objects.all()[:5].only('title', 'category', 'description', 'created_at'),
        'reviews': Review.objects.filter(approved=True)[:6].only('customer_name', 'review', 'rating', 'created_at'),
        'gallery': valid_gallery[:8],
        'charges': ServiceCharge.objects.select_related('service').all()[:3].only('service__name', 'charge'),
    }
    return render(request, 'homepage.html', context)


@cache_page(60 * 15)
def about(request):
    business = get_business()
    certifications = []
    if business and business.certifications:
        certifications = business.certifications.splitlines()

    team_members = TeamMember.objects.filter(is_active=True).order_by('order', 'name')

    context = {
        'business': business,
        'services': Service.objects.filter(active=True).only('name', 'icon'),
        'charges': ServiceCharge.objects.select_related('service').all().only('service__name', 'charge'),
        'certifications': certifications,
        'team_members': team_members,
    }
    return render(request, 'aboutus.html', context)


@cache_page(60 * 15)
def team(request):
    members = TeamMember.objects.filter(is_active=True).order_by('order', 'name').only(
        'id', 'name', 'designation', 'bio', 'photo'
    )
    paginator = Paginator(members, 12)
    page = request.GET.get('page')
    try:
        members_page = paginator.page(page)
    except PageNotAnInteger:
        members_page = paginator.page(1)
    except EmptyPage:
        members_page = paginator.page(paginator.num_pages)
    return render(request, 'team.html', {
        'business': get_business(),
        'members': members_page,
    })


def services(request):
    services_qs = Service.objects.filter(active=True).order_by('name').only('id', 'name', 'description', 'icon', 'icon_color')
    paginator = Paginator(services_qs, 12)
    page = request.GET.get('page')
    try:
        services_page = paginator.page(page)
    except PageNotAnInteger:
        services_page = paginator.page(1)
    except EmptyPage:
        services_page = paginator.page(paginator.num_pages)
    return render(request, 'services.html', {
        'business': get_business(),
        'services': services_page,
    })


def service_detail(request, slug):
    # The sitemap/templates build slugs with slugify(name); names containing
    # punctuation (e.g. "PAN & Aadhaar") cannot be recovered via name__iexact, so
    # match on the slugified name instead of 404-ing.
    service = Service.objects.filter(active=True, name__iexact=slug.replace('-', ' ')).first()
    if service is None:
        service = next((s for s in Service.objects.filter(active=True) if slugify(s.name) == slug.lower()), None)
    if service is None:
        raise Http404("Service not found")
    return render(request, 'service_detail.html', {
        'business': get_business(),
        'service': service,
        'charge': get_service_charge(service),
        'required_docs': RequiredDocument.objects.filter(service=service).order_by('document_name'),
    })


def gallery(request):
    all_images = Gallery.objects.all().order_by('-id')
    valid_images = [
        img for img in all_images
        if img.image and default_storage.exists(img.image.name)
    ]
    paginator = Paginator(valid_images, 12)
    page = request.GET.get('page')
    try:
        images_page = paginator.page(page)
    except PageNotAnInteger:
        images_page = paginator.page(1)
    except EmptyPage:
        images_page = paginator.page(paginator.num_pages)
    return render(request, 'gallery.html', {
        'business': get_business(),
        'images': images_page,
    })


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()
            send_admin_notification(
                subject=f"New Contact Message from {contact.name}",
                message=(
                    f'Name: {contact.name}\n'
                    f'Email: {contact.email}\n'
                    f'Phone: {contact.phone}\n'
                    f'Message:\n{contact.message}'
                )
            )
            messages.success(request, "Your message has been sent successfully.")
            return redirect('contact')
    else:
        form = ContactForm()
    return render(request, 'contactus.html', {
        'business': get_business(),
        'form': form,
    })


def appointment(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save()
            send_admin_notification(
                subject=f"New Appointment from {appointment.full_name}",
                message=(
                    f'Name: {appointment.full_name}\n'
                    f'Phone: {appointment.phone}\n'
                    f'Email: {appointment.email}\n'
                    f'Service: {appointment.service.name}\n'
                    f'Date: {appointment.appointment_date} at {appointment.appointment_time}\n'
                    f'Message: {appointment.message}'
                )
            )
            messages.success(request, "Appointment booked successfully.")
            return redirect('appointment')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AppointmentForm()
    return render(request, 'appointment.html', {
        'business': get_business(),
        'form': form,
        'services': Service.objects.filter(active=True).only('id', 'name'),
    })


@cache_page(60 * 60)
def faq(request):
    return render(request, 'faq.html', {
        'business': get_business(),
        'faqs': FAQ.objects.all().only('question', 'answer'),
    })


def documents(request):
    documents_qs = RequiredDocument.objects.select_related('service').all().only(
        'id', 'service__name', 'document_name'
    ).order_by('service__name', 'document_name')
    paginator = Paginator(documents_qs, 20)
    page = request.GET.get('page')
    try:
        documents_page = paginator.page(page)
    except PageNotAnInteger:
        documents_page = paginator.page(1)
    except EmptyPage:
        documents_page = paginator.page(paginator.num_pages)
    return render(request, 'required_document.html', {
        'business': get_business(),
        'documents_page': documents_page,
    })


def downloads(request):
    forms_qs = DownloadForm.objects.all().order_by('-uploaded_at').only('id', 'title', 'category', 'pdf')
    paginator = Paginator(forms_qs, 20)
    page = request.GET.get('page')
    try:
        forms_page = paginator.page(page)
    except PageNotAnInteger:
        forms_page = paginator.page(1)
    except EmptyPage:
        forms_page = paginator.page(paginator.num_pages)
    return render(request, 'download_forms.html', {
        'business': get_business(),
        'forms': forms_page,
    })


def charges(request):
    charges_qs = ServiceCharge.objects.select_related('service').only('id', 'service__name', 'charge')
    paginator = Paginator(charges_qs, 20)
    page = request.GET.get('page')
    try:
        charges_page = paginator.page(page)
    except PageNotAnInteger:
        charges_page = paginator.page(1)
    except EmptyPage:
        charges_page = paginator.page(paginator.num_pages)
    return render(request, 'service_charges.html', {
        'business': get_business(),
        'charges': charges_page,
    })


def reviews(request):
    all_reviews = Review.objects.filter(approved=True).order_by('-created_at').only(
        'id', 'customer_name', 'review', 'rating', 'created_at'
    )
    paginator = Paginator(all_reviews, 10)
    page = request.GET.get('page')
    try:
        reviews_page = paginator.page(page)
    except PageNotAnInteger:
        reviews_page = paginator.page(1)
    except EmptyPage:
        reviews_page = paginator.page(paginator.num_pages)

    total_reviews = all_reviews.count()
    if total_reviews > 0:
        rating_avg = all_reviews.aggregate(avg=models.Avg('rating'))['avg']
        rating_counts = {}
        for i in range(1, 6):
            rating_counts[i] = all_reviews.filter(rating=i).count()
    else:
        rating_avg = 0
        rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    return render(request, 'customer_reviews.html', {
        'business': get_business(),
        'reviews_page': reviews_page,
        'form': ReviewForm(),
        'rating_avg': rating_avg,
        'total_reviews': total_reviews,
        'rating_counts': rating_counts,
    })


def submit_review(request):
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.approved = False
            review.save()
            messages.success(request, "Thank you! Your review will appear after admin approval.")
        else:
            messages.error(request, "Please correct the errors in the review form.")
    return redirect('reviews')


def announcements(request):
    announcements_qs = Announcement.objects.all().order_by('-created_at').only(
        'id', 'title', 'category', 'description', 'created_at'
    )
    paginator = Paginator(announcements_qs, 10)
    page = request.GET.get('page')
    try:
        announcements_page = paginator.page(page)
    except PageNotAnInteger:
        announcements_page = paginator.page(1)
    except EmptyPage:
        announcements_page = paginator.page(paginator.num_pages)
    return render(request, 'announcements.html', {
        'business': get_business(),
        'announcements': announcements_page,
    })

def get_apply_link(scheme_dict):
    """Return a valid http(s) link, or a Google search fallback."""
    for key in ('apply_link', 'official_link'):
        link = (scheme_dict.get(key) or '').strip()
        if link.lower().startswith(('http://', 'https://')):
            return link
    title = (scheme_dict.get('title') or '').strip()
    query = f"{title} Maharashtra government scheme"
    return f"https://www.google.com/search?q={quote(query)}"


def _scheme_image_url(image):
    """Safe image URL or '' (a missing/removed file must not break the card)."""
    try:
        if image and image.name:
            return image.url
    except Exception:
        pass
    return ''


def government_schemes(request):
    # ----- 1. Fetch external schemes (cached, never raises) -----
    try:
        external_schemes = fetch_all_external_schemes()
    except Exception:
        logger.exception("External scheme fetch failed")
        external_schemes = []

    # ----- 2. Manual schemes from database (shown first) -----
    manual_schemes = GovernmentScheme.objects.filter(verified=True).order_by('-created_at')

    combined, seen = [], set()

    def add(d):
        key = re.sub(r'[^a-z0-9\u0900-\u097f]+', '', (d.get('title') or '').lower())
        if not key or key in seen:
            return
        seen.add(key)
        d['apply_link_display'] = get_apply_link(d)
        d['has_direct_link'] = d['apply_link_display'].startswith(('http://', 'https://')) and 'google.com/search' not in d['apply_link_display']
        d['eligibility'] = (d.get('eligibility') or '').strip() or 'Check the official website for eligibility'
        d['description'] = (d.get('description') or '').strip() or 'Open the official page for full details, required documents and how to apply.'
        combined.append(d)

    for scheme in manual_schemes:
        add({
            'title': scheme.title, 'description': scheme.description, 'eligibility': scheme.eligibility,
            'last_date': scheme.last_date, 'status': scheme.status, 'provider': scheme.provider,
            'department': scheme.department, 'image_url': _scheme_image_url(scheme.image),
            'apply_link': scheme.apply_link, 'official_link': scheme.official_link, 'source': 'manual',
        })
    for scheme in external_schemes:
        add({
            'title': scheme.get('title', ''), 'description': scheme.get('description', ''),
            'eligibility': scheme.get('eligibility', ''), 'last_date': scheme.get('last_date'),
            'status': scheme.get('status', 'active'), 'provider': scheme.get('provider', 'Government'),
            'department': scheme.get('department', ''), 'image_url': '',
            'apply_link': scheme.get('apply_link', ''), 'official_link': scheme.get('official_link', ''),
            'source': scheme.get('source', 'external'),
        })

    # ----- 3. Paginate (9 items per page = 3x3 grid) -----
    paginator = Paginator(combined, 9)
    page = request.GET.get('page')
    try:
        schemes_page = paginator.page(page)
    except PageNotAnInteger:
        schemes_page = paginator.page(1)
    except EmptyPage:
        schemes_page = paginator.page(paginator.num_pages)

    return render(request, 'government_schemes.html', {
        'business': get_business(),
        'schemes': schemes_page,
    })


def jobs(request):
    # ----- 1. Fetch external jobs (cached) -----
    external_jobs = fetch_all_external_jobs()

    # ----- 2. Fetch manual jobs from database -----
    manual_jobs = JobNotification.objects.filter(verified=True).order_by('-last_date')

    # ----- 3. Combine into a single list of dicts -----
    combined = []
    for job in manual_jobs:
        combined.append({
            'title': job.title,
            'organization': job.organization,
            'description': job.description,
            'apply_link': job.apply_link,
            'last_date': job.last_date,
            'source': 'manual',
        })

    for job in external_jobs:
        combined.append({
            'title': job.get('title', ''),
            'organization': job.get('organization', 'Various'),
            'description': job.get('description', ''),
            'apply_link': job.get('apply_link', '#'),
            'last_date': job.get('last_date'),
            'source': 'external',
        })

    # ----- 4. Normalize all dates to datetime.date (convert datetime -> date) -----
    for job in combined:
        if job.get('last_date') is not None:
            if isinstance(job['last_date'], datetime):
                job['last_date'] = job['last_date'].date()

    # ----- 5. Sort by last_date descending (newest first) -----
    combined.sort(
        key=lambda x: x.get('last_date') or datetime.min.date(),
        reverse=True
    )

    # ----- 6. Paginate (10 items per page) -----
    paginator = Paginator(combined, 9)
    page = request.GET.get('page')
    try:
        jobs_page = paginator.page(page)
    except PageNotAnInteger:
        jobs_page = paginator.page(1)
    except EmptyPage:
        jobs_page = paginator.page(paginator.num_pages)

    return render(request, 'jobs.html', {
        'business': get_business(),
        'jobs': jobs_page,
    })


# =============================================================================
# APPLICATION & DOCUMENT VIEWS (User) - updated for mandatory payment
# =============================================================================

@login_required
def apply_service(request, service_id):
    service = get_object_or_404(Service, id=service_id, active=True)

    # Check existing pending application
    existing = Application.objects.filter(
        user=request.user,
        service=service,
        status__in=['pending', 'review']
    ).exists()
    if existing:
        messages.error(request, "You already have a pending application for this service.")
        return redirect('my_applications')

    required_docs = RequiredDocument.objects.filter(service=service)

    initial_data = {
        'full_name': request.user.get_full_name() or request.user.username,
        'phone': request.user.phone or '',
        'email': request.user.email,
        'address': request.user.address or '',
    }

    DocumentFormSet = formset_factory(DocumentUploadForm, extra=len(required_docs), max_num=len(required_docs))

    if request.method == 'POST':
        form = ApplicationForm(request.POST)
        formset = DocumentFormSet(request.POST, request.FILES)
        if form.is_valid() and formset.is_valid():
            # Create application (with payment pending if required)
            application = form.save(commit=False)
            application.user = request.user
            application.service = service
            application.status = 'pending'
            application.payment_status = 'pending'
            application.save()
            ApplicationStatusHistory.objects.create(application=application, old_status='', new_status='pending', changed_by=request.user, note='Application submitted')
            notify_user(request.user, f"Application {application.application_number} submitted", f"Your {service.name} application has been submitted.", application)

            # Save documents
            for i, doc_form in enumerate(formset.cleaned_data):
                if doc_form:
                    doc_name = required_docs[i].document_name if i < len(required_docs) else 'Other'
                    DocumentUpload.objects.create(
                        application=application,
                        document_name=doc_name,
                        file=doc_form['file'],
                        is_mandatory=True,
                    )

            # If payment is required, redirect to checkout
            if service.payment_required:
                request.session['pending_app_id'] = application.id
                return redirect('payment_checkout', app_id=application.id)
            else:
                # No payment required – success
                send_admin_notification(
                    subject=f"New Application for {service.name} from {application.full_name}",
                    message=(
                        f'Name: {application.full_name}\n'
                        f'Phone: {application.phone}\n'
                        f'Email: {application.email}\n'
                        f'Service: {service.name}\n'
                        f'Address: {application.address}'
                    )
                )
                messages.success(request, "Your application has been submitted successfully.")
                return redirect('application_detail', app_id=application.id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ApplicationForm(initial=initial_data)
        initial_docs = [{'document_name': doc.document_name} for doc in required_docs]
        formset = DocumentFormSet(initial=initial_docs)

    return render(request, 'apply_service.html', {
        'service': service,
        'required_docs': required_docs,
        'form': form,
        'formset': formset,
        'business': get_business(),
        'payment_settings': get_payment_settings(),
        'payment_required': service.payment_required,
    })


@login_required
@require_POST
def create_razorpay_order(request):
    app_id = request.POST.get('app_id')
    if not app_id:
        return JsonResponse({'error': 'Application ID missing'}, status=400)

    application = get_object_or_404(Application, id=app_id, user=request.user)
    if getattr(settings, 'PAYMENT_GATEWAY', 'manual') != 'razorpay' or not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return JsonResponse({'error': 'Online gateway is not configured. Please use manual UPI or cash.'}, status=503)
    if application.payment_status == 'paid':
        return JsonResponse({'error': 'Payment already completed'}, status=400)

    charge = get_service_charge(application.service)
    if not charge:
        return JsonResponse({'error': 'No charge defined for this service'}, status=400)

    # Compute breakdown
    breakdown = compute_payment_breakdown(
        charge.charge,
        gst_rate=getattr(settings, 'GST_RATE', 0.18),
        fee_percent=getattr(settings, 'RAZORPAY_FEE_PERCENT', 2.0),
        fee_fixed=getattr(settings, 'RAZORPAY_FEE_FIXED', 0.0)
    )
    total_amount = breakdown['total']
    amount_in_paise = int(total_amount * 100)

    # Create Razorpay order
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    order_data = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'receipt': f'app_{application.id}',
        'payment_capture': 1,
        'notes': {
            'application_id': application.id,
            'user_id': application.user.id,
            'service_amount': str(breakdown['service_amount']),
            'fee': str(breakdown['fee']),
            'gst_on_fee': str(breakdown['gst_on_fee']),
            'total': str(breakdown['total']),
        }
    }
    try:
        order = client.order.create(data=order_data)
    except Exception as e:
        logger.error(f"Razorpay order creation failed: {e}")
        return JsonResponse({'error': 'Failed to create order. Please try again.'}, status=500)

    application.razorpay_order_id = order['id']
    application.service_amount = breakdown['service_amount']
    application.razorpay_fee = breakdown['fee']
    application.gst_on_fee = breakdown['gst_on_fee']
    application.total_paid = breakdown['total']
    application.save(update_fields=['razorpay_order_id', 'service_amount', 'razorpay_fee', 'gst_on_fee', 'total_paid'])

    return JsonResponse({
        'order_id': order['id'],
        'amount': amount_in_paise,
        'currency': 'INR',
        'key': settings.RAZORPAY_KEY_ID,
        'app_id': application.id,
        'breakdown': {
            'service_amount': str(breakdown['service_amount']),
            'fee': str(breakdown['fee']),
            'gst_on_fee': str(breakdown['gst_on_fee']),
            'total': str(breakdown['total']),
        }
    })


@login_required
@require_POST
def payment_success(request):
    app_id = request.GET.get('app_id')
    if not app_id:
        messages.error(request, "Application ID missing.")
        return redirect('services')

    application = get_object_or_404(Application, id=app_id, user=request.user)

    # Get Razorpay response from POST (Razorpay sends as POST)
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_signature = request.POST.get('razorpay_signature')

    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
        messages.error(request, "Incomplete payment verification data.")
        return redirect('application_detail', app_id=application.id)
    if not application.razorpay_order_id or not hmac.compare_digest(
        str(application.razorpay_order_id), str(razorpay_order_id)
    ):
        audit(request, 'razorpay_payment_order_mismatch', application, {'order_id': str(razorpay_order_id)[:100]})
        messages.error(request, "Payment verification failed. Please contact support.")
        return redirect('application_detail', app_id=application.id)
    if application.payment_status == 'paid':
        if application.razorpay_payment_id == razorpay_payment_id:
            messages.success(request, "This payment has already been confirmed.")
        else:
            messages.error(request, "This application is already marked as paid.")
        return redirect('application_detail', app_id=application.id)

    # Verify signature
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }
    try:
        client.utility.verify_payment_signature(params_dict)
    except razorpay.errors.SignatureVerificationError:
        logger.warning(f"Payment signature verification failed for app {app_id}")
        messages.error(request, "Payment verification failed. Please contact support.")
        return redirect('application_detail', app_id=application.id)

    # Preserve the expected amount saved when the order was created. This avoids
    # changes to tax/fee settings between order creation and payment completion
    # changing the amount used for the receipt.
    if application.total_paid is None or application.service_amount is None:
        charge = get_service_charge(application.service)
        if charge:
            breakdown = compute_payment_breakdown(
                charge.charge,
                gst_rate=getattr(settings, 'GST_RATE', 0.18),
                fee_percent=getattr(settings, 'RAZORPAY_FEE_PERCENT', 2.0),
                fee_fixed=getattr(settings, 'RAZORPAY_FEE_FIXED', 0.0)
            )
            application.service_amount = breakdown['service_amount']
            application.razorpay_fee = breakdown['fee']
            application.gst_on_fee = breakdown['gst_on_fee']
            application.total_paid = breakdown['total']
        else:
            application.service_amount = Decimal('0.00')
            application.razorpay_fee = Decimal('0.00')
            application.gst_on_fee = Decimal('0.00')
            application.total_paid = Decimal('0.00')

    # Update application
    application.razorpay_payment_id = razorpay_payment_id
    application.razorpay_signature = razorpay_signature
    application.payment_status = 'paid'
    application.payment_date = timezone.now()
    application.payment_method = 'razorpay'
    application.receipt_number = application.generate_receipt_number()
    application.save()

    # Create payment log
    PaymentLog.objects.create(
        application=application,
        event_type='captured',
        amount=application.total_paid or 0,
    )
    notify_user(application.user, f"Payment received for {application.application_number}", f"Your payment for {application.service.name} has been received.", application)
    audit(request, 'razorpay_payment_captured', application, {'payment_id': razorpay_payment_id})

    # Send confirmation email
    send_payment_confirmation(application)

    messages.success(request, "Payment successful! Your application is now confirmed.")
    return redirect('application_detail', app_id=application.id)


@login_required
def payment_failure(request):
    app_id = request.GET.get('app_id')
    if not app_id:
        messages.error(request, "Application ID missing.")
        return redirect('services')

    application = get_object_or_404(Application, id=app_id, user=request.user)
    PaymentLog.objects.create(
        application=application,
        event_type='failed',
        amount=0,
    )
    messages.error(request, "Payment was unsuccessful. You can try again from your applications.")
    return redirect('application_detail', app_id=application.id)


@login_required
def payment_checkout(request, app_id):
    application = get_object_or_404(Application, id=app_id, user=request.user)
    if application.payment_status == 'paid':
        messages.warning(request, "This application has already been paid.")
        return redirect('application_detail', app_id=app_id)

    charge = get_service_charge(application.service)
    if not charge:
        messages.error(request, "No charge defined for this service.")
        return redirect('application_detail', app_id=app_id)

    razorpay_enabled = bool(getattr(settings, 'PAYMENT_GATEWAY', 'manual') == 'razorpay' and settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
    breakdown = compute_payment_breakdown(
        charge.charge,
        gst_rate=getattr(settings, 'GST_RATE', 0.18),
        fee_percent=getattr(settings, 'RAZORPAY_FEE_PERCENT', 2.0) if razorpay_enabled else 0,
        fee_fixed=getattr(settings, 'RAZORPAY_FEE_FIXED', 0.0) if razorpay_enabled else 0,
    )

    context = {
        'application': application,
        'business': get_business(),
        'payment_settings': get_payment_settings(),
        'razorpay_key': settings.RAZORPAY_KEY_ID,
        'breakdown': breakdown,
        'razorpay_enabled': razorpay_enabled,
    }
    return render(request, 'payment_checkout.html', context)


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """Process only signed, captured Razorpay events and make them idempotent."""
    import hashlib
    import hmac

    if settings.PAYMENT_GATEWAY != 'razorpay' or not settings.RAZORPAY_WEBHOOK_SECRET:
        return JsonResponse({'error': 'Webhook is not configured.'}, status=503)

    supplied_signature = request.headers.get('X-Razorpay-Signature', '')
    expected_signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8'), request.body, hashlib.sha256
    ).hexdigest()
    if not supplied_signature or not hmac.compare_digest(supplied_signature, expected_signature):
        logger.warning('Rejected Razorpay webhook with an invalid signature')
        audit(request, 'razorpay_webhook_signature_rejected', details={'provider': 'razorpay'})
        return JsonResponse({'error': 'Invalid signature.'}, status=401)

    try:
        event_payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)
    if not isinstance(event_payload, dict):
        return JsonResponse({'error': 'Webhook payload must be a JSON object.'}, status=400)

    event_name = event_payload.get('event', '')
    if event_name != 'payment.captured':
        audit(request, 'razorpay_webhook_ignored', details={'event': str(event_name)[:80]})
        return JsonResponse({'status': 'ignored'})

    payload_wrapper = event_payload.get('payload') or {}
    payment_wrapper = payload_wrapper.get('payment', {}) if isinstance(payload_wrapper, dict) else {}
    payment = (payment_wrapper.get('entity') or {}) if isinstance(payment_wrapper, dict) else {}
    if not isinstance(payment, dict):
        return JsonResponse({'error': 'Payment payload is invalid.'}, status=400)
    order_id = payment.get('order_id')
    payment_id = payment.get('id')
    if not order_id or not payment_id or payment.get('status') != 'captured':
        return JsonResponse({'error': 'Captured payment details are missing.'}, status=400)

    try:
        application = Application.objects.select_related('user', 'service').get(razorpay_order_id=order_id)
    except Application.DoesNotExist:
        audit(request, 'razorpay_webhook_unknown_order', details={'order_id': str(order_id)[:100]})
        return JsonResponse({'error': 'Unknown order.'}, status=404)

    # Verify amount and currency against the server-stored order total. Never
    # trust the webhook's amount alone to choose the amount recorded as paid.
    try:
        incoming_amount = int(payment.get('amount'))
        expected_amount = int(Decimal(str(application.total_paid)) * 100)
    except (TypeError, ValueError, ArithmeticError):
        return JsonResponse({'error': 'Payment amount is invalid.'}, status=400)
    if payment.get('currency') != 'INR' or incoming_amount != expected_amount:
        audit(request, 'razorpay_webhook_amount_mismatch', application, {
            'order_id': str(order_id)[:100], 'currency': str(payment.get('currency', ''))[:8]
        })
        return JsonResponse({'error': 'Payment amount did not match the order.'}, status=400)

    with transaction.atomic():
        application = Application.objects.select_for_update().select_related('user', 'service').get(pk=application.pk)
        if application.payment_status == 'paid':
            if application.razorpay_payment_id == payment_id:
                return JsonResponse({'status': 'already_processed'})
            audit(request, 'razorpay_webhook_duplicate_payment_rejected', application, {'order_id': str(order_id)[:100]})
            return JsonResponse({'error': 'Order has already been paid.'}, status=409)
        application.razorpay_payment_id = payment_id
        application.payment_status = 'paid'
        application.payment_date = timezone.now()
        application.payment_method = 'razorpay'
        if not application.receipt_number:
            application.receipt_number = application.generate_receipt_number()
        application.save(update_fields=[
            'razorpay_payment_id', 'payment_status', 'payment_date', 'payment_method', 'receipt_number'
        ])
        PaymentLog.objects.create(application=application, event_type='captured', amount=application.total_paid or 0)

    audit(request, 'razorpay_payment_captured_webhook', application, {'payment_id': str(payment_id)[:100]})
    notify_user(application.user, f'Payment received for {application.application_number}',
                f'Your payment for {application.service.name} has been received.', application)
    send_payment_confirmation(application)
    return JsonResponse({'status': 'processed'})


def track_application(request):
    application = None
    if request.method == 'POST' or request.GET.get('application_number'):
        number = (request.POST.get('application_number') or request.GET.get('application_number') or '').strip()
        phone = (request.POST.get('phone') or request.GET.get('phone') or '').strip()
        if number and phone:
            application = Application.objects.filter(application_number__iexact=number, phone=phone).select_related('service').first()
            if not application:
                messages.error(request, 'No application matched that application number and phone number.')
    return render(request, 'track_application.html', {'business': get_business(), 'application': application})


@login_required
def notifications(request):
    items = Notification.objects.filter(user=request.user).select_related('application')[:50]
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return render(request, 'notifications.html', {'business': get_business(), 'notifications': items})


@login_required
def document_download(request, doc_id):
    document = get_object_or_404(DocumentUpload.objects.select_related('application__user'), id=doc_id)
    if not (is_admin(request.user) or document.application.user_id == request.user.id):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    if not document.file:
        messages.error(request, 'This document is unavailable.')
        return redirect('application_detail', app_id=document.application_id)
    try:
        stored_basename = os.path.basename(document.file.name)
        if stored_basename.endswith('.enc'):
            stored_basename = stored_basename[:-4]
        extension = os.path.splitext(stored_basename)[1].lower()
        if extension not in {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.doc', '.docx', '.xls', '.xlsx', '.odt', '.ods', '.txt', '.csv'}:
            extension = ''
        # Use the admin-defined document label rather than exposing the original
        # user-supplied filename or the random encrypted storage identifier.
        safe_label = re.sub(r'[^A-Za-z0-9_-]+', '-', document.document_name).strip('-_').lower()[:80]
        download_name = f"{safe_label or f'document-{document.pk}'}{extension}"
        response = FileResponse(document.file.open('rb'), as_attachment=True, filename=download_name)
        return response
    except Exception:
        messages.error(request, 'Unable to open this document.')
        return redirect('application_detail', app_id=document.application_id)


@login_required
def my_applications(request):
    applications = Application.objects.filter(user=request.user).order_by('-created_at').only(
        'id', 'application_number', 'service__name', 'status', 'payment_status', 'created_at'
    ).select_related('service')
    paginator = Paginator(applications, 10)
    page = request.GET.get('page')
    try:
        apps_page = paginator.page(page)
    except PageNotAnInteger:
        apps_page = paginator.page(1)
    except EmptyPage:
        apps_page = paginator.page(paginator.num_pages)
    return render(request, 'my_applications.html', {
        'applications': apps_page,
        'business': get_business(),
    })


@login_required
def application_detail(request, app_id):
    application = get_object_or_404(
        Application.objects.select_related('service', 'user'),
        id=app_id,
        user=request.user
    )
    documents = application.documents.all().only('id', 'document_name', 'file', 'verified', 'verification_status', 'verification_note', 'uploaded_at')
    return render(request, 'application_detail.html', {
        'application': application,
        'documents': documents,
        'status_history': application.status_history.select_related('changed_by').all(),
        'business': get_business(),
        'payment_settings': get_payment_settings(),
        'payment_required': application.service.payment_required,
    })


# =============================================================================
# APPLICATION & DOCUMENT VIEWS (Admin)
# =============================================================================

@login_required
@user_passes_test(is_admin)
def application_detail_ajax(request, app_id):
    app = get_object_or_404(Application, id=app_id)
    documents = app.documents.all().only('id', 'document_name', 'file', 'verified', 'verification_status')
    data = {
        'full_name': app.full_name,
        'phone': app.phone,
        'email': app.email,
        'address': app.address,
        'service': app.service.name,
        'status': app.get_status_display(),
        'created_at': app.created_at.strftime("%d %b %Y, %H:%M"),
        'documents': [
            {
                'name': doc.document_name,
                'url': reverse('document_download', kwargs={'doc_id': doc.id}),
                'verified': doc.verified,
            }
            for doc in documents
        ]
    }
    return JsonResponse(data)


@login_required
@user_passes_test(is_admin)
def application_admin_detail(request, app_id):
    application = get_object_or_404(
        Application.objects.select_related('service', 'user'),
        id=app_id
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_status':
            new_status = request.POST.get('status')
            if new_status in dict(Application.STATUS_CHOICES):
                old_status = application.status
                note = request.POST.get('note', '').strip()
                application.status = new_status
                application.admin_note = note or application.admin_note
                if new_status == 'rejected':
                    application.rejection_reason = note
                application.save()
                if old_status != new_status:
                    ApplicationStatusHistory.objects.create(application=application, old_status=old_status, new_status=new_status, changed_by=request.user, note=note)
                    notify_user(application.user, f"Application {application.application_number} updated", f"Your application status changed from {old_status.title()} to {application.get_status_display()}." + (f" Note: {note}" if note else ''), application)
                audit(request, 'application_status_changed', application, {'old_status': old_status, 'new_status': new_status})
                messages.success(request, "Status updated successfully.")
            else:
                messages.error(request, "Invalid status.")
            return redirect('application_admin_detail', app_id=app_id)

        elif action == 'delete_document':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(DocumentUpload, id=doc_id, application=application)
            doc.delete()
            messages.success(request, "Document deleted.")
            return redirect('application_admin_detail', app_id=app_id)

        elif action == 'add_document':
            doc_name = request.POST.get('document_name', '').strip()
            upload_form = DocumentUploadForm({'document_name': doc_name}, request.FILES)
            if doc_name and upload_form.is_valid():
                doc = upload_form.save(commit=False)
                doc.application = application
                doc.is_mandatory = False
                doc.save()
                audit(request, 'admin_document_uploaded', doc)
                messages.success(request, "Document uploaded.")
            else:
                messages.error(request, "Please provide a valid document name and PDF/JPG/PNG file under the size limit.")
            return redirect('application_admin_detail', app_id=app_id)

        elif action == 'verify_document':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(DocumentUpload, id=doc_id, application=application)
            new_doc_status = request.POST.get('verification_status', 'pending')
            if new_doc_status not in ('pending', 'verified', 'rejected'):
                messages.error(request, 'Invalid document status.')
                return redirect('application_admin_detail', app_id=app_id)
            doc.verification_status = new_doc_status
            doc.verified = new_doc_status == 'verified'
            doc.verified_by = request.user if doc.verified else None
            doc.verified_at = timezone.now() if doc.verified else None
            doc.verification_note = request.POST.get('verification_note', '').strip()
            doc.save()
            audit(request, 'document_verification_changed', doc, {'status': new_doc_status})
            messages.success(request, "Document verification updated.")
            return redirect('application_admin_detail', app_id=app_id)

        elif action == 'mark_payment_paid':
            if application.payment_status != 'paid':
                application.payment_status = 'paid'
                application.payment_date = timezone.now()
                application.receipt_number = application.generate_receipt_number()
                application.payment_method = application.payment_method or 'manual'
                charge = get_service_charge(application.service)
                application.service_amount = charge.charge if charge else 0
                application.razorpay_fee = 0
                application.gst_on_fee = 0
                application.total_paid = application.service_amount
                application.save()
                PaymentLog.objects.create(
                    application=application,
                    event_type='manual_confirmed',
                    amount=charge.charge if charge else 0,
                )
                notify_user(application.user, f"Payment received for {application.application_number}", f"Your payment for {application.service.name} was marked as paid.", application)
                audit(request, 'manual_payment_confirmed', application)
                send_payment_confirmation(application)
                messages.success(request, "Payment marked as paid manually.")
            else:
                messages.warning(request, "Payment already paid.")
            return redirect('application_admin_detail', app_id=app_id)

    payment_settings = get_payment_settings()

    context = {
        'application': application,
        'documents': application.documents.all().only(
            'id', 'document_name', 'file', 'is_mandatory', 'verified', 'verification_status', 'verification_note', 'verified_at', 'uploaded_at'
        ),
        'business': get_business(),
        'payment_settings': payment_settings,
    }
    return render(request, 'application_admin_detail.html', context)


# =============================================================================
# PDF SPLITTING VIEW
# =============================================================================

@login_required
@user_passes_test(is_admin)
def split_pdf(request, pk):
    document = get_object_or_404(DocumentUpload, pk=pk)
    app = document.application

    if request.method == 'POST':
        pages_input = request.POST.get('pages', '').strip()
        if not pages_input:
            return render(request, 'split_pdf.html', {
                'document': document,
                'app': app,
                'error': "Please enter page numbers.",
            })

        try:
            with default_storage.open(document.file.name, 'rb') as f:
                reader = PdfReader(f)
                writer = PdfWriter()
                total_pages = len(reader.pages)

                selected_pages = []
                parts = pages_input.split(',')
                for part in parts:
                    part = part.strip()
                    if '-' in part:
                        start, end = part.split('-')
                        start = int(start)
                        end = int(end)
                        if start < 1 or end > total_pages or start > end:
                            raise ValueError
                        for p in range(start, end + 1):
                            selected_pages.append(p)
                    else:
                        p = int(part)
                        if p < 1 or p > total_pages:
                            raise ValueError
                        selected_pages.append(p)

                selected_pages = sorted(set(selected_pages))

                for page_num in selected_pages:
                    writer.add_page(reader.pages[page_num - 1])

                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as tmp:
                    writer.write(tmp)
                    tmp.seek(0)
                    response = FileResponse(
                        tmp,
                        as_attachment=True,
                        filename=f"split_{os.path.basename(document.file.name)[:-4] if document.file.name.endswith('.enc') else os.path.basename(document.file.name)}",
                    )
                    response._resource_closers = [lambda: tmp.close()]
                    return response

        except (ValueError, IndexError, Exception) as e:
            logger.warning(f"PDF split error: {e}")
            return render(request, 'split_pdf.html', {
                'document': document,
                'app': app,
                'error': "Invalid page numbers.",
            })

    return render(request, 'split_pdf.html', {
        'document': document,
        'app': app,
        'business': get_business(),
    })


# =============================================================================
# PAYMENT GATEWAY - UPI ONLY (Manual fallback)
# =============================================================================

@login_required
@require_POST
def mark_payment_done(request, app_id):
    """Manual payment confirmation (UPI or Cash) – kept for admin override."""
    # Helper to validate UPI details
    def validate_upi_details(method, payment_app, utr):
        if method != 'upi':
            return True, None
        if not payment_app:
            return False, "Please select a payment app."
        if not utr:
            return False, "UTR number is required for UPI payments."
        if not re.match(r'^[A-Za-z0-9]{12,16}$', utr):
            return False, "Invalid UTR format. It must be 12-16 alphanumeric characters."
        return True, None

    # Check if this is a pending application (app_id == 0)
    if app_id == 0:
        pending_data = request.session.get('pending_application', None)
        if not pending_data:
            messages.error(request, "No pending application found.")
            return redirect('services')

        service = get_object_or_404(Service, id=pending_data['service_id'])
        payment_settings = get_payment_settings()
        method = request.POST.get('payment_method', 'upi')
        if method == 'upi' and not payment_settings.upi_enabled:
            messages.error(request, "UPI payments are not enabled.")
            return redirect('payment_checkout', service_id=service.id)
        if method == 'cash' and not payment_settings.cash_enabled:
            messages.error(request, "Cash payments are not enabled.")
            return redirect('payment_checkout', service_id=service.id)

        utr = request.POST.get('utr_number', '').strip()
        payment_app = request.POST.get('payment_app', '').strip()

        valid, error_msg = validate_upi_details(method, payment_app, utr)
        if not valid:
            messages.error(request, error_msg)
            return redirect('payment_checkout', service_id=service.id)

        pending_data['payment_method'] = method
        pending_data['utr_number'] = utr
        pending_data['payment_app'] = payment_app
        request.session['pending_application'] = pending_data

        try:
            application = _create_application_from_session_data(pending_data, request)
        except Exception as e:
            logger.error(f"Application creation failed: {e}")
            request.session.pop('pending_application', None)
            messages.error(request, str(e) or "Failed to create application.")
            return redirect('services')

        request.session.pop('pending_application', None)
        messages.success(request, "Your application has been submitted and payment confirmed.")
        return redirect('application_detail', app_id=application.id)

    # --- Existing application (app_id > 0) ---
    application = get_object_or_404(Application, id=app_id, user=request.user)

    if application.payment_status == 'paid':
        messages.warning(request, "Payment already processed.")
        return redirect('application_detail', app_id=app_id)

    payment_settings = get_payment_settings()
    method = request.POST.get('payment_method', 'upi')
    if method == 'upi' and not payment_settings.upi_enabled:
        messages.error(request, "UPI payments are not enabled.")
        return redirect('application_detail', app_id=app_id)
    if method == 'cash' and not payment_settings.cash_enabled:
        messages.error(request, "Cash payments are not enabled.")
        return redirect('application_detail', app_id=app_id)

    time_limit = timezone.now() - timedelta(hours=24)
    if application.created_at < time_limit:
        messages.error(request, "Payment window expired. Please contact admin.")
        return redirect('application_detail', app_id=app_id)

    utr = request.POST.get('utr_number', '').strip()
    payment_app = request.POST.get('payment_app', '').strip()

    valid, error_msg = validate_upi_details(method, payment_app, utr)
    if not valid:
        messages.error(request, error_msg)
        return redirect('application_detail', app_id=app_id)

    application.payment_status = 'pending'
    application.payment_method = method
    application.utr_number = utr
    application.payment_app = payment_app
    application.payment_transaction_id = utr or ''
    application.save()

    charge = get_service_charge(application.service)
    PaymentLog.objects.create(
        application=application,
        event_type='manual_submitted',
        amount=charge.charge if charge else 0,
    )
    notify_user(application.user, f"Payment submitted for {application.application_number}", "Your payment details were submitted and are awaiting admin verification.", application)
    audit(request, 'manual_payment_submitted', application, {'method': method, 'utr': utr})
    send_admin_notification(
        subject=f"Payment verification required - {application.application_number}",
        message=f"{application.full_name} submitted {method} payment for {application.service.name}. UTR: {utr or 'Not provided'}."
    )
    messages.success(request, "Payment details submitted. The center will verify your payment.")
    cache.delete('reports_data')
    return redirect('application_detail', app_id=app_id)


# =============================================================================
# HELPER: create application from session (used for UPI fallback)
# =============================================================================

@transaction.atomic
def _create_application_from_session_data(pending_data, request):
    """
    Internal helper to create an Application from session data.
    Returns the created Application object.
    Raises: Exception if duplicate application already exists.
    """
    service = get_object_or_404(Service, id=pending_data['service_id'])
    form_data = pending_data['form_data']
    temp_files = pending_data['temp_files']

    existing = Application.objects.filter(
        user=request.user,
        service=service,
        status__in=['pending', 'review']
    ).first()
    if existing:
        raise Exception("You already have a pending application for this service.")

    payment_method = pending_data.get('payment_method', 'upi')
    payment_app = pending_data.get('payment_app', '')
    utr_number = pending_data.get('utr_number', '')

    application = Application(
        user=request.user,
        service=service,
        full_name=form_data['full_name'],
        phone=form_data['phone'],
        email=form_data['email'],
        address=form_data['address'],
        extra_data=form_data.get('extra_data', {}),
        status='pending',
        payment_status='pending',
        payment_date=None,
        payment_method=payment_method,
        payment_app=payment_app,
        utr_number=utr_number,
        payment_transaction_id='',
    )
    application.save()
    ApplicationStatusHistory.objects.create(application=application, old_status='', new_status='pending', changed_by=request.user, note='Application submitted')
    notify_user(request.user, f"Application {application.application_number} submitted", f"Your {service.name} application and payment have been recorded.", application)

    # Save documents from local temp files
    for temp in temp_files:
        try:
            with open(temp['temp_path'], 'rb') as f:
                doc = DocumentUpload(
                    application=application,
                    document_name=temp['document_name'],
                    is_mandatory=True,
                )
                doc.file.save(temp['original_name'], File(f), save=False)
                doc.save()
            os.unlink(temp['temp_path'])
        except Exception as e:
            logger.error(f"Failed to save document {temp['document_name']}: {e}")
            raise

    send_admin_notification(
        subject=f"New Application for {service.name} from {application.full_name} (Paid)",
        message=(
            f'Name: {application.full_name}\n'
            f'Phone: {application.phone}\n'
            f'Email: {application.email}\n'
            f'Service: {service.name}\n'
            f'Address: {application.address}\n'
            f'Receipt: {application.receipt_number}'
        )
    )

    return application


@login_required
def create_application_from_session(request):
    pending_data = request.session.pop('pending_application', None)
    if not pending_data:
        messages.error(request, "No pending application found.")
        return redirect('services')

    try:
        application = _create_application_from_session_data(pending_data, request)
        messages.success(request, "Your application has been submitted and payment confirmed.")
        return redirect('application_detail', app_id=application.id)
    except Exception as e:
        logger.error(f"Application creation failed: {e}")
        for temp in pending_data.get('temp_files', []):
            try:
                os.unlink(temp['temp_path'])
            except OSError:
                pass
        messages.error(request, str(e) or "Failed to create application. Please contact support.")
        return redirect('services')


def get_pending_application_from_session(request):
    return request.session.get('pending_application', None)


# =============================================================================
# RECEIPT DOWNLOAD
# =============================================================================

@login_required
def download_receipt(request, app_id):
    application = get_object_or_404(Application, id=app_id, user=request.user)
    if application.payment_status != 'paid':
        messages.error(request, "No payment record found.")
        return redirect('application_detail', app_id=app_id)

    # ---- Data ----
    charge = get_service_charge(application.service)
    if not charge:
        messages.error(request, "Service charge missing.")
        return redirect('application_detail', app_id=app_id)

    # Use the amount actually recorded at payment time; manual UPI/cash has no gateway fee.
    service_amount = application.service_amount or charge.charge
    fee = application.razorpay_fee or Decimal('0.00')
    gst_on_fee = application.gst_on_fee or Decimal('0.00')
    total_amount = application.total_paid or (service_amount + fee + gst_on_fee)

    business = get_business()

    # ---- QR Code (disabled) ----
    qr_img = None

    # ---- Find and register the font ----
    possible_font_paths = [
        os.path.join(settings.BASE_DIR, 'static', 'fonts', 'dejavu-fonts-ttf-2.37', 'ttf', 'DejaVuSans.ttf'),
        os.path.join(settings.BASE_DIR, 'static', 'fonts', 'dejavu-fonts-ttf-2.37', 'DejaVuSans.ttf'),
        os.path.join(settings.BASE_DIR, 'static', 'fonts', 'DejaVuSans.ttf'),
        os.path.join(settings.BASE_DIR, 'corematoshree', 'static', 'fonts', 'DejaVuSans.ttf'),
    ]
    font_name = 'Helvetica'
    for font_path in possible_font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
                font_name = 'DejaVuSans'
                logger.info(f"Loaded font from {font_path}")
                break
            except Exception as e:
                logger.warning(f"Failed to load font from {font_path}: {e}")
    if font_name == 'Helvetica':
        logger.warning("DejaVuSans not found, using Helvetica. Rs. sign may not display correctly.")

    # ---- PDF setup ----
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.6*inch,
        leftMargin=0.6*inch,
        topMargin=0.6*inch,
        bottomMargin=0.6*inch,
    )

    styles = getSampleStyleSheet()

    def create_style(name, parent, **kwargs):
        return ParagraphStyle(name, parent=styles[parent], fontName=font_name, **kwargs)

    brand_style = create_style('BrandStyle', 'Heading1', fontSize=22, textColor=colors.HexColor('#1a1a2e'), alignment=TA_LEFT, spaceAfter=2)
    sub_style = create_style('SubStyle', 'Normal', fontSize=9, textColor=colors.HexColor('#64748b'), alignment=TA_LEFT, spaceAfter=1)
    receipt_title_style = create_style('ReceiptTitle', 'Heading2', fontSize=16, textColor=colors.HexColor('#0f172a'), alignment=TA_CENTER, spaceAfter=4)
    success_style = create_style('SuccessStyle', 'Heading2', fontSize=14, textColor=colors.HexColor('#16a34a'), alignment=TA_CENTER, spaceAfter=6)
    amount_style = create_style('AmountStyle', 'Heading1', fontSize=32, textColor=colors.HexColor('#2563eb'), alignment=TA_CENTER, spaceAfter=8)
    section_title = create_style('SectionTitle', 'Heading4', fontSize=11, textColor=colors.HexColor('#334155'), alignment=TA_LEFT, spaceAfter=4, spaceBefore=8)
    label_style = create_style('LabelStyle', 'Normal', fontSize=9, textColor=colors.HexColor('#94a3b8'), alignment=TA_LEFT, spaceAfter=2)
    value_style = create_style('ValueStyle', 'Normal', fontSize=9, textColor=colors.HexColor('#0f172a'), alignment=TA_LEFT, spaceAfter=2)
    total_style = create_style('TotalStyle', 'Normal', fontSize=12, textColor=colors.HexColor('#0f172a'), alignment=TA_RIGHT, spaceAfter=2)
    footer_style = create_style('FooterStyle', 'Normal', fontSize=8, textColor=colors.HexColor('#94a3b8'), alignment=TA_CENTER, spaceAfter=2)
    normal_style = create_style('NormalStyle', 'Normal', fontSize=9, textColor=colors.HexColor('#0f172a'), alignment=TA_LEFT)

    story = []

    # ---- Header ----
    logo_img = None
    if business and business.logo:
        try:
            if default_storage.exists(business.logo.name):
                with default_storage.open(business.logo.name, 'rb') as f:
                    logo_img = Image(f, width=1.2*inch, height=1.2*inch)
        except Exception as e:
            logger.warning(f"Could not load logo: {e}")
            logo_img = None

    if logo_img:
        header_data = [[logo_img, Paragraph(f"<b>{business.business_name}</b>", brand_style)]]
        header_table = Table(header_data, colWidths=[1.5*inch, 4.5*inch])
    else:
        header_data = [[Paragraph(f"<b>{business.business_name}</b>", brand_style)]]
        header_table = Table(header_data, colWidths=[6*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)

    # Business details
    details = []
    if business and business.address:
        details.append(f"Address: {business.address}")
    if business and business.phone:
        details.append(f"Phone: {business.phone}")
    if business and business.email:
        details.append(f"Email: {business.email}")
    if business and business.gstin:
        details.append(f"GSTIN: {business.gstin}")
    elif business and business.registration_number:
        details.append(f"Reg. No.: {business.registration_number}")

    if details:
        story.append(Paragraph("  |  ".join(details), sub_style))

    story.append(Spacer(1, 0.15*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0'), spaceBefore=2, spaceAfter=2))

    # ---- Title ----
    story.append(Paragraph("PAYMENT RECEIPT", receipt_title_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(HRFlowable(width="60%", thickness=1, color=colors.HexColor('#3b82f6'), spaceBefore=2, spaceAfter=4))

    # ---- Status & Amount ----
    story.append(Paragraph("Payment Successful", success_style))
    story.append(Paragraph(f"₹ {total_amount:,.2f}", amount_style))
    story.append(HRFlowable(width="40%", thickness=1, color=colors.HexColor('#22c55e'), spaceBefore=2, spaceAfter=6))

    # ---- Transaction Details (Razorpay specific) ----
    trans_data = [
        ["Receipt No.", application.receipt_number or 'N/A'],
        ["Date & Time", application.payment_date.strftime('%d %b %Y, %I:%M %p') if application.payment_date else 'N/A'],
        ["Razorpay Payment ID", application.razorpay_payment_id or 'N/A'],
        ["Payment Method", application.get_payment_method_display() or 'N/A'],
    ]
    trans_table = Table([[Paragraph(f"<b>{label}</b>", label_style), Paragraph(value, value_style)] for label, value in trans_data],
                        colWidths=[2.2*inch, 3.8*inch])
    trans_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), font_name),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(trans_table)
    story.append(Spacer(1, 0.15*inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceBefore=2, spaceAfter=2))

    # ---- Breakdown Table (replaces old GST tax logic) ----
    breakdown_rows = [
        ['Service Charge', f'₹{service_amount:,.2f}'],
        ['Razorpay Fee', f'₹{fee:,.2f}'],
        ['GST on Fee (18%)', f'₹{gst_on_fee:,.2f}'],
        ['Total', f'₹{total_amount:,.2f}'],
    ]
    breakdown_table = Table(breakdown_rows, colWidths=[4*inch, 2*inch])
    breakdown_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), font_name),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 5),
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor('#0f172a')),
        ('FONTNAME', (0,-1), (-1,-1), font_name),
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor('#0f172a')),
        ('FONTSIZE', (0,-1), (-1,-1), 12),
    ]))
    story.append(breakdown_table)
    story.append(Spacer(1, 0.15*inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceBefore=2, spaceAfter=2))

    # ---- Customer & Service Details ----
    customer_data = [
        [Paragraph("<b>Customer Details</b>", section_title)],
        [Paragraph(f"Name: {application.full_name}", value_style)],
        [Paragraph(f"Phone: {application.phone}", value_style)],
        [Paragraph(f"Email: {application.email}", value_style)],
        [Paragraph(f"Address: {application.address}", value_style)],
    ]
    cust_table = Table(customer_data, colWidths=[3*inch])
    cust_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 3),
        ('FONTNAME', (0,0), (-1,-1), font_name),
    ]))

    service_data = [
        [Paragraph("<b>Service Details</b>", section_title)],
        [Paragraph(f"Service: {application.service.name}", value_style)],
        [Paragraph(f"Service Charge: ₹{service_amount:,.2f}", value_style)],
        [Paragraph(f"Total Paid: ₹{total_amount:,.2f}", value_style)],
        [Paragraph("Status: Paid", value_style)],
    ]
    serv_table = Table(service_data, colWidths=[3*inch])
    serv_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 3),
        ('FONTNAME', (0,0), (-1,-1), font_name),
    ]))

    combined = Table([[cust_table, serv_table]], colWidths=[3*inch, 3*inch])
    combined.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(combined)
    story.append(Spacer(1, 0.15*inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceBefore=2, spaceAfter=2))

    # ---- QR Code (disabled) ----
    if qr_img:
        qr_table = Table([[qr_img]], colWidths=[1.5*inch])
        qr_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(qr_table)
        story.append(Paragraph("Scan to verify", normal_style))
        story.append(Spacer(1, 0.1*inch))

    # ---- Footer ----
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0'), spaceBefore=4, spaceAfter=4))
    story.append(Paragraph("Thank you for your payment. This is a system-generated receipt.", footer_style))
    story.append(Paragraph(f"Verified on: {timezone.now().strftime('%d %b %Y %I:%M %p')}", footer_style))
    support_email = business.email if business and business.email else 'the center'
    story.append(Paragraph(f"For support, contact us at {support_email}", footer_style))
    story.append(Paragraph(f"© {timezone.now().year} {business.business_name if business else 'Matoshree Cyber Center'}. All rights reserved.", footer_style))

    doc.build(story)
    buffer.seek(0)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"receipt_{application.receipt_number}.pdf"
    )


# =============================================================================
# DASHBOARD REPORT
# =============================================================================

@login_required
@user_passes_test(is_admin)
def reports_dashboard(request):
    cache_key = 'reports_data'
    data = cache.get(cache_key)

    if not data:
        app_status_counts = list(Application.objects.values('status').annotate(count=Count('id')))
        if not app_status_counts:
            app_status_counts = [{'status': 'No Data', 'count': 0}]

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        daily_apps = list(
            Application.objects.filter(created_at__date__gte=start_date)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        if not daily_apps:
            daily_apps = [{'day': start_date, 'count': 0}]

        appt_status_counts = list(Appointment.objects.values('status').annotate(count=Count('id')))
        if not appt_status_counts:
            appt_status_counts = [{'status': 'No Data', 'count': 0}]

        weekly_users = list(
            User.objects.filter(date_joined__gte=timezone.now() - timedelta(days=90))
            .annotate(week=TruncWeek('date_joined'))
            .values('week')
            .annotate(count=Count('id'))
            .order_by('week')
        )
        if not weekly_users:
            weekly_users = [{'week': timezone.now().date() - timedelta(days=7), 'count': 0}]

        payment_status_counts = list(Application.objects.values('payment_status').annotate(count=Count('id')))
        if not payment_status_counts:
            payment_status_counts = [{'payment_status': 'No Data', 'count': 0}]

        data = {
            'app_status': app_status_counts,
            'daily_apps': daily_apps,
            'appt_status': appt_status_counts,
            'weekly_users': weekly_users,
            'payment_status': payment_status_counts,
        }
        cache.set(cache_key, data, 300)

    data_json = json.dumps(data, default=str)

    context = {
        'data_json': data_json,
        'business': get_business(),
    }
    return render(request, 'reports_dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def export_applications_csv(request):
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="applications.csv"'
    writer = csv.writer(response)
    writer.writerow(['Application Number', 'Customer', 'Phone', 'Email', 'Service', 'Status', 'Payment Status', 'Created At'])
    for app in Application.objects.select_related('service').order_by('-created_at'):
        writer.writerow([app.application_number, app.full_name, app.phone, app.email, app.service.name, app.get_status_display(), app.get_payment_status_display(), app.created_at.strftime('%Y-%m-%d %H:%M')])
    audit(request, 'applications_csv_exported')
    return response


# =============================================================================
# STATIC PAGES - Terms & Privacy
# =============================================================================

def terms(request):
    return render(request, 'terms.html', {
        'business': get_business(),
    })


def privacy(request):
    return render(request, 'privacy.html', {
        'business': get_business(),
    })

