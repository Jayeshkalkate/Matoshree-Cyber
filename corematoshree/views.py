# =============================================================================
# IMPORTS
# =============================================================================
import os
import json
import tempfile
import logging
from datetime import timedelta
from io import BytesIO

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView,
    PasswordResetCompleteView
)
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import models
from django.db.models import Count, Q
from django.db.models.functions import ExtractWeek, TruncDate
from django.forms import formset_factory
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.conf import settings
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import razorpay

from .models import (
    User, Appointment, Review, Service, Announcement, JobNotification,
    GovernmentScheme, DownloadForm, ServiceCharge, Gallery, BusinessInfo,
    RequiredDocument, FAQ, Application, DocumentUpload, Contact, TeamMember,
    PaymentSettings, PaymentLog,
)
from .forms import (
    TeamMemberForm, CustomUserCreationForm, ProfileUpdateForm, ContactForm,
    AppointmentForm, ReviewForm, ServiceForm, AnnouncementForm,
    JobNotificationForm, GovernmentSchemeForm, AppointmentFormDashboard,
    ContactFormDashboard, DownloadFormForm, ServiceChargeForm, GalleryForm,
    BusinessInfoForm, RequiredDocumentForm, ApplicationForm, DocumentUploadForm,
    PaymentSettingsForm,
)

logger = logging.getLogger(__name__)

# =============================================================================
# HELPERS (with caching)
# =============================================================================

def get_business():
    """Cache BusinessInfo to avoid repeated DB hits."""
    cache_key = 'business_info'
    business = cache.get(cache_key)
    if business is None:
        try:
            business = BusinessInfo.objects.first()
        except Exception:
            business = None
        cache.set(cache_key, business, 60 * 60)  # 1 hour
    return business


def get_payment_settings():
    """Cache PaymentSettings to avoid repeated DB hits."""
    cache_key = 'payment_settings'
    settings_obj = cache.get(cache_key)
    if settings_obj is None:
        settings_obj = PaymentSettings.objects.filter(is_active=True).first()
        if not settings_obj:
            # Create a default inactive instance if none exists
            settings_obj = PaymentSettings.objects.create(is_active=False)
        cache.set(cache_key, settings_obj, 60 * 60)
    return settings_obj


def is_admin(user):
    return user.is_authenticated and user.role in ('admin', 'superadmin')


def is_superadmin(user):
    return user.is_authenticated and user.role == 'superadmin'


def send_admin_notification(subject, message, recipient_list=None):
    """Send email to admin(s)."""
    if recipient_list is None:
        recipient_list = [getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL)]
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")


def send_welcome_email(user):
    """Send welcome email to new user."""
    try:
        send_mail(
            subject=_("Welcome to our platform"),
            message=_(
                f"Hi {user.username},\n\n"
                "Thank you for registering. You can now book appointments and apply for services.\n"
                "Visit our website to get started."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")


def send_payment_confirmation(application):
    """Send payment confirmation email to user and admin."""
    try:
        charge = application.service.servicecharge_set.first()
        amount = charge.charge if charge else 0
        business_name = get_business().business_name if get_business() else 'Cyber Cafe'

        send_mail(
            subject=_('Payment Confirmed – Application #{}').format(application.id),
            message=_('''
Dear {name},

Your payment for {service} has been confirmed.
Receipt No: {receipt}
Amount Paid: ₹{amount}

Thank you for choosing our services.

Regards,
{business}
            ''').format(
                name=application.full_name,
                service=application.service.name,
                receipt=application.receipt_number,
                amount=amount,
                business=business_name
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.email],
            fail_silently=True,
        )
        # Admin notification
        send_admin_notification(
            subject=f'Payment Received – {application.full_name}',
            message=f'Payment of ₹{amount} received for {application.service.name}.\nReceipt: {application.receipt_number}'
        )
    except Exception as e:
        logger.error(f"Failed to send payment confirmation email: {e}")


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, _('Account created successfully!'))
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
            messages.success(request, _('Profile updated successfully!'))
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, 'profile.html', {
        'form': form,
        'business': get_business(),
    })


# -----------------------------------------------------------------------------
# Password Reset Views
# -----------------------------------------------------------------------------
class CustomPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'registration/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'registration/password_reset_complete.html'


# =============================================================================
# DASHBOARD (ADMIN & SUPERADMIN)
# =============================================================================

DASHBOARD_CACHE_KEY = 'dashboard_data_v2'
DASHBOARD_CACHE_TTL = 120  # 2 minutes


def _get_dashboard_common_data():
    cache_key = DASHBOARD_CACHE_KEY
    cached = cache.get(cache_key)

    payment_settings_instance = PaymentSettings.objects.filter(is_active=True).first()
    if not payment_settings_instance:
        payment_settings_instance = PaymentSettings.objects.first()
        if not payment_settings_instance:
            payment_settings_instance = PaymentSettings.objects.create(is_active=False)

    if cached is not None:
        data = cached
    else:
        data = {
            'services': Service.objects.all().only('id', 'name', 'category', 'active', 'icon', 'icon_color'),
            'appointments': Appointment.objects.select_related('service').only(
                'id', 'full_name', 'phone', 'email', 'service__name',
                'appointment_date', 'appointment_time', 'status', 'created_at'
            ).order_by('-appointment_date')[:50],
            'contacts': Contact.objects.all().only('id', 'name', 'email', 'phone', 'subject', 'message', 'reply', 'replied', 'created_at'),
            'announcements': Announcement.objects.all().only('id', 'title', 'category', 'description', 'created_at'),
            'jobs': JobNotification.objects.all().only('id', 'title', 'organization', 'last_date', 'apply_link', 'description', 'icon'),
            'schemes': GovernmentScheme.objects.all().only('id', 'title', 'description', 'eligibility', 'last_date', 'image'),
            'forms_list': DownloadForm.objects.all().only('id', 'title', 'category', 'pdf', 'uploaded_at'),
            'servicecharges': ServiceCharge.objects.select_related('service').only('id', 'service__name', 'charge'),
            'gallery_images': Gallery.objects.all().only('id', 'title', 'category', 'image'),
            'business_info': BusinessInfo.objects.first(),
            'applications': Application.objects.select_related('user', 'service').only(
                'id', 'user__username', 'service__name', 'full_name', 'phone',
                'email', 'address', 'status', 'created_at'
            ).order_by('-created_at')[:50],
            'required_docs': RequiredDocument.objects.select_related('service').only(
                'id', 'service__name', 'document_name'
            ).order_by('service__name'),
            'team_members': TeamMember.objects.all().order_by('order', 'name'),
        }
        cache.set(cache_key, data, DASHBOARD_CACHE_TTL)

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

def _handle_add(model_type, request, is_super):
    if model_type == 'service':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Service added.'))
        else:
            messages.error(request, _('Error adding service.'))
    elif model_type == 'requireddoc':
        raw_docs = request.POST.get('document_name', '').strip()
        service_id = request.POST.get('service')
        if not service_id:
            messages.error(request, _('Please select a service.'))
            return
        doc_names = [name.strip() for name in raw_docs.split(',') if name.strip()]
        if not doc_names:
            messages.error(request, _('Please enter at least one document name.'))
            return
        service = get_object_or_404(Service, id=service_id)
        created = 0
        for doc_name in doc_names:
            doc_obj, created_flag = RequiredDocument.objects.get_or_create(
                service=service, document_name=doc_name
            )
            if created_flag:
                created += 1
        messages.success(request, _('{count} document(s) added for “{service}”.').format(
            count=created, service=service.name
        ))
    elif model_type == 'teammember':
        form = TeamMemberForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, _('Team member added.'))
        else:
            messages.error(request, _('Error adding team member.'))
    elif model_type == 'announcement':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Announcement added.'))
        else:
            messages.error(request, _('Error adding announcement.'))
    elif model_type == 'job':
        form = JobNotificationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Job notification added.'))
        else:
            messages.error(request, _('Error adding job.'))
    elif model_type == 'scheme':
        form = GovernmentSchemeForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, _('Scheme added.'))
        else:
            messages.error(request, _('Error adding scheme.'))
    elif model_type == 'appointment':
        form = AppointmentFormDashboard(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Appointment added.'))
        else:
            messages.error(request, _('Error adding appointment.'))
    elif model_type == 'contact':
        form = ContactFormDashboard(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Contact added.'))
        else:
            messages.error(request, _('Error adding contact.'))
    elif model_type == 'form':
        form = DownloadFormForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, _('Download form uploaded.'))
        else:
            messages.error(request, _('Error uploading form.'))
    elif model_type == 'servicecharge':
        form = ServiceChargeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Service charge added.'))
        else:
            messages.error(request, _('Error adding service charge.'))
    elif model_type == 'gallery':
        form = GalleryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, _('Gallery image uploaded.'))
        else:
            messages.error(request, _('Error uploading gallery image.'))
    else:
        messages.error(request, _('Unknown model type for add.'))


def _handle_edit(model_type, obj_id, request):
    if model_type == 'service':
        instance = get_object_or_404(Service, id=obj_id)
        form = ServiceForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Service updated.'))
        else:
            messages.error(request, _('Error updating service.'))
    elif model_type == 'requireddoc':
        instance = get_object_or_404(RequiredDocument, id=obj_id)
        form = RequiredDocumentForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Required document updated.'))
        else:
            messages.error(request, _('Error updating required document.'))
    elif model_type == 'teammember':
        instance = get_object_or_404(TeamMember, id=obj_id)
        form = TeamMemberForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Team member updated.'))
        else:
            messages.error(request, _('Error updating team member.'))
    elif model_type == 'announcement':
        instance = get_object_or_404(Announcement, id=obj_id)
        form = AnnouncementForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Announcement updated.'))
        else:
            messages.error(request, _('Error updating announcement.'))
    elif model_type == 'job':
        instance = get_object_or_404(JobNotification, id=obj_id)
        form = JobNotificationForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Job updated.'))
        else:
            messages.error(request, _('Error updating job.'))
    elif model_type == 'scheme':
        instance = get_object_or_404(GovernmentScheme, id=obj_id)
        form = GovernmentSchemeForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Scheme updated.'))
        else:
            messages.error(request, _('Error updating scheme.'))
    elif model_type == 'appointment':
        instance = get_object_or_404(Appointment, id=obj_id)
        form = AppointmentFormDashboard(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Appointment updated.'))
        else:
            messages.error(request, _('Error updating appointment.'))
    elif model_type == 'contact':
        instance = get_object_or_404(Contact, id=obj_id)
        if 'reply' in request.POST:
            reply_text = request.POST.get('reply')
            instance.reply = reply_text
            instance.replied = True
            instance.save()
            try:
                send_mail(
                    subject=_("Reply to your inquiry"),
                    message=_(f"Dear {instance.name},\n\nThank you for contacting us. Here is our reply:\n\n{reply_text}\n\nBest regards,\n{get_business().business_name if get_business() else 'Team'}"),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[instance.email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f"Failed to send reply email: {e}")
            messages.success(request, _('Reply saved and email sent to customer.'))
        else:
            form = ContactFormDashboard(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, _('Contact updated.'))
            else:
                messages.error(request, _('Error updating contact.'))
    elif model_type == 'form':
        instance = get_object_or_404(DownloadForm, id=obj_id)
        form = DownloadFormForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Form updated.'))
        else:
            messages.error(request, _('Error updating form.'))
    elif model_type == 'servicecharge':
        instance = get_object_or_404(ServiceCharge, id=obj_id)
        form = ServiceChargeForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Service charge updated.'))
        else:
            messages.error(request, _('Error updating service charge.'))
    elif model_type == 'businessinfo':
        instance = get_object_or_404(BusinessInfo, id=obj_id)
        form = BusinessInfoForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _('Business info updated.'))
            cache.delete('business_info')
        else:
            messages.error(request, _('Error updating business info.'))
    else:
        messages.error(request, _('Unknown model type for edit.'))


def _handle_delete(model_type, obj_id, request):
    if model_type == 'service':
        get_object_or_404(Service, id=obj_id).delete()
        messages.success(request, _('Service deleted.'))
    elif model_type == 'announcement':
        get_object_or_404(Announcement, id=obj_id).delete()
        messages.success(request, _('Announcement deleted.'))
    elif model_type == 'teammember':
        get_object_or_404(TeamMember, id=obj_id).delete()
        messages.success(request, _('Team member deleted.'))
    elif model_type == 'requireddoc':
        get_object_or_404(RequiredDocument, id=obj_id).delete()
        messages.success(request, _('Required document deleted.'))
    elif model_type == 'job':
        get_object_or_404(JobNotification, id=obj_id).delete()
        messages.success(request, _('Job deleted.'))
    elif model_type == 'scheme':
        get_object_or_404(GovernmentScheme, id=obj_id).delete()
        messages.success(request, _('Scheme deleted.'))
    elif model_type == 'appointment':
        get_object_or_404(Appointment, id=obj_id).delete()
        messages.success(request, _('Appointment deleted.'))
    elif model_type == 'contact':
        get_object_or_404(Contact, id=obj_id).delete()
        messages.success(request, _('Contact deleted.'))
    elif model_type == 'form':
        get_object_or_404(DownloadForm, id=obj_id).delete()
        messages.success(request, _('Form deleted.'))
    elif model_type == 'servicecharge':
        get_object_or_404(ServiceCharge, id=obj_id).delete()
        messages.success(request, _('Service charge deleted.'))
    elif model_type == 'gallery':
        get_object_or_404(Gallery, id=obj_id).delete()
        messages.success(request, _('Gallery image deleted.'))
    else:
        messages.error(request, _('Unknown model type for delete.'))


def _handle_payment_settings(request):
    instance = PaymentSettings.objects.first() or PaymentSettings()
    form = PaymentSettingsForm(request.POST, request.FILES, instance=instance)
    if form.is_valid():
        payment_settings = form.save(commit=False)
        payment_settings.is_active = True
        payment_settings.save()
        messages.success(request, _('Payment settings updated.'))
        cache.delete('payment_settings')
    else:
        logger.error(f"PaymentSettings form errors: {form.errors.as_json()}")
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        messages.error(request, _('Please correct the errors below.'))
    cache.delete(DASHBOARD_CACHE_KEY)


def _handle_user_role_edit(request):
    user_id = request.POST.get('user_id')
    new_role = request.POST.get('new_role')
    if user_id and new_role:
        user = get_object_or_404(User, id=user_id)
        user.role = new_role
        user.save()
        messages.success(request, _('User role updated.'))
    cache.delete(DASHBOARD_CACHE_KEY)


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

    elif model_type == 'paymentsettings':
        _handle_payment_settings(request)
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
    return render(request, 'admindashboard.html', context)


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
    return render(request, 'superadmindashboard.html', context)


@login_required
@user_passes_test(is_admin)
def dashboard_section_data(request, section):
    data = {}
    if section == 'services':
        data['services'] = list(Service.objects.values('id', 'name', 'category', 'active', 'icon', 'icon_color'))
    elif section == 'appointments':
        data['appointments'] = list(Appointment.objects.select_related('service').values(
            'id', 'full_name', 'phone', 'email', 'service__name',
            'appointment_date', 'appointment_time', 'status', 'created_at'
        ).order_by('-appointment_date'))
    elif section == 'contacts':
        data['contacts'] = list(Contact.objects.values('id', 'name', 'email', 'phone', 'subject', 'message', 'reply', 'replied', 'created_at'))
    elif section == 'announcements':
        data['announcements'] = list(Announcement.objects.values('id', 'title', 'category', 'description', 'created_at'))
    elif section == 'jobs':
        data['jobs'] = list(JobNotification.objects.values('id', 'title', 'organization', 'last_date', 'apply_link', 'description', 'icon'))
    elif section == 'schemes':
        data['schemes'] = list(GovernmentScheme.objects.values('id', 'title', 'description', 'eligibility', 'last_date', 'image'))
    elif section == 'forms':
        data['forms'] = list(DownloadForm.objects.values('id', 'title', 'category', 'pdf', 'uploaded_at'))
    elif section == 'servicecharges':
        data['servicecharges'] = list(ServiceCharge.objects.select_related('service').values(
            'id', 'service__name', 'charge'))
    elif section == 'gallery':
        data['gallery'] = list(Gallery.objects.values('id', 'title', 'category', 'image'))
    elif section == 'requireddocs':
        data['requireddocs'] = list(RequiredDocument.objects.select_related('service').values(
            'id', 'service__name', 'document_name'))
    elif section == 'applications':
        data['applications'] = list(Application.objects.select_related('user', 'service').values(
            'id', 'user__username', 'service__name', 'full_name', 'phone',
            'email', 'address', 'status', 'created_at'
        ).order_by('-created_at'))
    elif section == 'users' and request.user.role == 'superadmin':
        data['users'] = list(User.objects.values('id', 'username', 'email', 'role', 'is_staff'))
    else:
        data['error'] = _('Invalid section.')
    return JsonResponse(data)


# =============================================================================
# PUBLIC VIEWS
# =============================================================================

@cache_page(60 * 5)
def home(request):
    context = {
        'business': get_business(),
        'services': Service.objects.filter(active=True)[:8].only('name', 'description', 'icon', 'icon_color'),
        'announcements': Announcement.objects.all()[:5].only('title', 'category', 'description', 'created_at'),
        'reviews': Review.objects.filter(approved=True)[:6].only('customer_name', 'review', 'rating', 'created_at'),
        'gallery': Gallery.objects.all()[:8].only('title', 'image'),
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


def gallery(request):
    images = Gallery.objects.all().order_by('-id').only('id', 'title', 'image')
    paginator = Paginator(images, 12)
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
                subject=f'New Contact Message from {contact.name}',
                message=(
                    f'Name: {contact.name}\n'
                    f'Email: {contact.email}\n'
                    f'Phone: {contact.phone}\n'
                    f'Message:\n{contact.message}'
                )
            )
            messages.success(request, _('Your message has been sent successfully.'))
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
                subject=f'New Appointment from {appointment.full_name}',
                message=(
                    f'Name: {appointment.full_name}\n'
                    f'Phone: {appointment.phone}\n'
                    f'Email: {appointment.email}\n'
                    f'Service: {appointment.service.name}\n'
                    f'Date: {appointment.appointment_date} at {appointment.appointment_time}\n'
                    f'Message: {appointment.message}'
                )
            )
            messages.success(request, _('Appointment booked successfully.'))
            return redirect('appointment')
        else:
            messages.error(request, _('Please correct the errors below.'))
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
    forms_qs = DownloadForm.objects.all().only('id', 'title', 'category', 'pdf')
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
            messages.success(request, _('Thank you! Your review will appear after admin approval.'))
        else:
            messages.error(request, _('Please correct the errors in the review form.'))
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


def government_schemes(request):
    schemes_qs = GovernmentScheme.objects.all().order_by('-last_date').only(
        'id', 'title', 'description', 'eligibility', 'last_date', 'image'
    )
    paginator = Paginator(schemes_qs, 10)
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
    jobs_qs = JobNotification.objects.order_by('last_date').only(
        'id', 'title', 'organization', 'last_date', 'apply_link', 'description', 'icon'
    )
    paginator = Paginator(jobs_qs, 10)
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
# APPLICATION & DOCUMENT VIEWS (User) – updated for mandatory payment
# =============================================================================

@login_required
def apply_service(request, service_id):
    service = get_object_or_404(Service, id=service_id, active=True)
    required_docs = RequiredDocument.objects.filter(service=service).only('id', 'document_name')

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
            if service.payment_required:
                # Save uploaded files temporarily
                temp_files = []
                for doc_form in formset.cleaned_data:
                    if doc_form and 'file' in doc_form:
                        f = doc_form['file']
                        # Save to temp location using default_storage
                        temp_path = default_storage.save(f'temp/{f.name}', ContentFile(f.read()))
                        temp_files.append({
                            'document_name': doc_form.get('document_name', 'Other'),
                            'temp_path': temp_path,
                            'original_name': f.name,
                        })
                # Store in session
                request.session['pending_application'] = {
                    'service_id': service.id,
                    'form_data': form.cleaned_data,
                    'temp_files': temp_files,
                }
                # Redirect to payment checkout
                return redirect('payment_checkout', service_id=service.id)
            else:
                # Payment not required – save immediately
                application = form.save(commit=False)
                application.user = request.user
                application.service = service
                application.save()

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

                send_admin_notification(
                    subject=f'New Application for {service.name} from {application.full_name}',
                    message=(
                        f'Name: {application.full_name}\n'
                        f'Phone: {application.phone}\n'
                        f'Email: {application.email}\n'
                        f'Service: {service.name}\n'
                        f'Address: {application.address}\n'
                        f'Documents uploaded: {len(required_docs)}'
                    )
                )

                messages.success(request, _('Your application has been submitted successfully.'))
                return render(request, 'apply_service.html', {
                    'service': service,
                    'required_docs': required_docs,
                    'form': form,
                    'formset': formset,
                    'application': application,
                    'business': get_business(),
                    'payment_settings': get_payment_settings(),
                })
        else:
            messages.error(request, _('Please correct the errors below.'))
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
def my_applications(request):
    applications = Application.objects.filter(user=request.user).order_by('-created_at').only(
        'id', 'service__name', 'status', 'created_at'
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
    documents = application.documents.all().only('id', 'document_name', 'file', 'verified')
    return render(request, 'application_detail.html', {
        'application': application,
        'documents': documents,
        'business': get_business(),
        'payment_settings': get_payment_settings(),
        'payment_required': application.service.payment_required,
    })


# =============================================================================
# PAYMENT CHECKOUT & SESSION HANDLING
# =============================================================================

@login_required
def payment_checkout(request, service_id):
    service = get_object_or_404(Service, id=service_id, active=True)
    pending_data = request.session.get('pending_application', None)
    if not pending_data or pending_data.get('service_id') != service.id:
        messages.error(request, _('No pending application found.'))
        return redirect('apply_service', service_id=service.id)

    return render(request, 'payment_checkout.html', {
        'service': service,
        'business': get_business(),
        'payment_settings': get_payment_settings(),
        'pending_application': pending_data,
    })


@login_required
def create_application_from_session(request):
    pending_data = request.session.pop('pending_application', None)
    if not pending_data:
        messages.error(request, _('No pending application found.'))
        return redirect('services')

    service = get_object_or_404(Service, id=pending_data['service_id'])
    form_data = pending_data['form_data']
    temp_files = pending_data['temp_files']

    # Create application
    application = Application(
        user=request.user,
        service=service,
        full_name=form_data['full_name'],
        phone=form_data['phone'],
        email=form_data['email'],
        address=form_data['address'],
        extra_data=form_data.get('extra_data', {}),
        status='pending',
        payment_status='paid',  # payment already confirmed
        payment_date=timezone.now(),
    )
    application.save()
    application.receipt_number = application.generate_receipt_number()
    application.save(update_fields=['receipt_number'])

    # Save documents from temp files
    from django.core.files import File
    for temp in temp_files:
        try:
            with open(temp['temp_path'], 'rb') as f:
                doc = DocumentUpload(
                    application=application,
                    document_name=temp['document_name'],
                    file=File(f, name=temp['original_name']),
                    is_mandatory=True,
                )
                doc.save()
            # Clean up temp file
            os.remove(temp['temp_path'])
        except Exception as e:
            logger.error(f"Failed to save document {temp['document_name']}: {e}")

    send_admin_notification(
        subject=f'New Application for {service.name} from {application.full_name} (Paid)',
        message=(
            f'Name: {application.full_name}\n'
            f'Phone: {application.phone}\n'
            f'Email: {application.email}\n'
            f'Service: {service.name}\n'
            f'Address: {application.address}\n'
            f'Receipt: {application.receipt_number}'
        )
    )

    messages.success(request, _('Your application has been submitted and payment confirmed.'))
    return redirect('application_detail', app_id=application.id)


def get_pending_application_from_session(request):
    """Return pending application data from session or None."""
    return request.session.get('pending_application', None)


# =============================================================================
# APPLICATION & DOCUMENT VIEWS (Admin)
# =============================================================================

@login_required
@user_passes_test(is_admin)
def application_detail_ajax(request, app_id):
    app = get_object_or_404(Application, id=app_id)
    documents = app.documents.all().only('document_name', 'file', 'verified')
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
                'url': doc.file.url,
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
                application.status = new_status
                application.save()
                messages.success(request, _('Status updated successfully.'))
            else:
                messages.error(request, _('Invalid status.'))
            return redirect('application_admin_detail', app_id=app_id)

        elif action == 'delete_document':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(DocumentUpload, id=doc_id, application=application)
            doc.delete()
            messages.success(request, _('Document deleted.'))
            return redirect('application_admin_detail', app_id=app_id)

        elif action == 'add_document':
            doc_name = request.POST.get('document_name')
            file = request.FILES.get('file')
            if doc_name and file:
                DocumentUpload.objects.create(
                    application=application,
                    document_name=doc_name,
                    file=file,
                    is_mandatory=False
                )
                messages.success(request, _('Document uploaded.'))
            else:
                messages.error(request, _('Please provide both name and file.'))
            return redirect('application_admin_detail', app_id=app_id)

        elif action == 'verify_document':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(DocumentUpload, id=doc_id, application=application)
            doc.verified = not doc.verified
            doc.save()
            messages.success(request, _('Document verification toggled.'))
            return redirect('application_admin_detail', app_id=app_id)

        elif action == 'mark_payment_paid':
            if application.payment_status != 'paid':
                application.payment_status = 'paid'
                application.payment_date = timezone.now()
                application.receipt_number = application.generate_receipt_number()
                application.payment_method = 'manual'
                application.save()
                PaymentLog.objects.create(
                    application=application,
                    event_type='manual_confirmed',
                    amount=application.service.servicecharge_set.first().charge,
                )
                send_payment_confirmation(application)
                messages.success(request, _('Payment marked as paid manually.'))
            else:
                messages.warning(request, _('Payment already paid.'))
            return redirect('application_admin_detail', app_id=app_id)

    payment_settings = get_payment_settings()

    context = {
        'application': application,
        'documents': application.documents.all().only(
            'id', 'document_name', 'file', 'is_mandatory', 'verified', 'uploaded_at'
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
                'error': _('Please enter page numbers.'),
            })

        try:
            reader = PdfReader(document.file.path)
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

            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                writer.write(tmp)
                tmp_path = tmp.name

            response = FileResponse(
                open(tmp_path, 'rb'),
                as_attachment=True,
                filename=f'split_{os.path.basename(document.file.name)}',
            )
            response._resource_closers = [lambda: os.unlink(tmp_path)]
            return response

        except (ValueError, IndexError, Exception) as e:
            logger.warning(f"PDF split error: {e}")
            return render(request, 'split_pdf.html', {
                'document': document,
                'app': app,
                'error': _('Invalid page numbers.'),
            })

    return render(request, 'split_pdf.html', {
        'document': document,
        'app': app,
        'business': get_business(),
    })


# =============================================================================
# PAYMENT GATEWAY – ENHANCED
# =============================================================================

@login_required
def create_razorpay_order(request, app_id, retry_count=0):
    """Create a Razorpay order for an existing application."""
    app = get_object_or_404(Application, id=app_id, user=request.user)

    if app.payment_status == 'paid':
        return JsonResponse({'error': 'Payment already completed'}, status=400)

    payment_settings = get_payment_settings()
    if not payment_settings or not payment_settings.razorpay_enabled:
        return JsonResponse({'error': 'Razorpay is not enabled'}, status=400)

    charge = app.service.servicecharge_set.first()
    if not charge:
        return JsonResponse({'error': 'No charge defined for this service'}, status=400)

    amount = int(charge.charge * 100)
    if amount < 100:
        return JsonResponse({'error': 'Amount must be at least ₹1'}, status=400)

    try:
        key = payment_settings.razorpay_test_key if payment_settings.test_mode else payment_settings.razorpay_key_id
        secret = payment_settings.razorpay_test_secret if payment_settings.test_mode else payment_settings.razorpay_key_secret
        client = razorpay.Client(auth=(key, secret))
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'receipt': f'app_{app.id}',
            'payment_capture': 1,
        }
        order = client.order.create(order_data)
    except Exception as e:
        logger.error(f"Razorpay order creation failed (attempt {retry_count+1}): {e}")
        if retry_count < 3:
            return create_razorpay_order(request, app_id, retry_count + 1)
        return JsonResponse({'error': 'Payment gateway temporarily unavailable. Please try again later.'}, status=503)

    app.payment_transaction_id = order['id']
    app.save()

    PaymentLog.objects.create(
        application=app,
        event_type='created',
        amount=charge.charge,
        razorpay_order_id=order['id'],
    )

    return JsonResponse({
        'order_id': order['id'],
        'amount': amount,
        'currency': 'INR',
        'key': key,
        'app_id': app.id,
    })


@login_required
def create_razorpay_order_pending(request, service_id, retry_count=0):
    """Create a Razorpay order for a pending (not yet saved) application."""
    pending_data = request.session.get('pending_application', None)
    if not pending_data or pending_data.get('service_id') != service_id:
        return JsonResponse({'error': 'No pending application found'}, status=400)

    service = get_object_or_404(Service, id=service_id)
    charge = service.servicecharge_set.first()
    if not charge:
        return JsonResponse({'error': 'No charge defined for this service'}, status=400)

    payment_settings = get_payment_settings()
    if not payment_settings or not payment_settings.razorpay_enabled:
        return JsonResponse({'error': 'Razorpay is not enabled'}, status=400)

    amount = int(charge.charge * 100)
    if amount < 100:
        return JsonResponse({'error': 'Amount must be at least ₹1'}, status=400)

    try:
        key = payment_settings.razorpay_test_key if payment_settings.test_mode else payment_settings.razorpay_key_id
        secret = payment_settings.razorpay_test_secret if payment_settings.test_mode else payment_settings.razorpay_key_secret
        client = razorpay.Client(auth=(key, secret))
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'receipt': f'pending_{service_id}_{request.user.id}',
            'payment_capture': 1,
        }
        order = client.order.create(order_data)
    except Exception as e:
        logger.error(f"Razorpay order creation failed (pending): {e}")
        if retry_count < 3:
            return create_razorpay_order_pending(request, service_id, retry_count + 1)
        return JsonResponse({'error': 'Payment gateway temporarily unavailable.'}, status=503)

    pending_data['razorpay_order_id'] = order['id']
    request.session['pending_application'] = pending_data

    return JsonResponse({
        'order_id': order['id'],
        'amount': amount,
        'currency': 'INR',
        'key': key,
        'service_id': service_id,
    })


@login_required
def verify_razorpay_payment(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    payment_id = request.POST.get('razorpay_payment_id')
    order_id = request.POST.get('razorpay_order_id')
    signature = request.POST.get('razorpay_signature')
    app_id = request.POST.get('app_id')

    if not all([payment_id, order_id, signature, app_id]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    # Check if this is a pending application (app_id is "pending" or 0)
    if app_id == 'pending' or app_id == '0':
        pending_data = request.session.get('pending_application', None)
        if not pending_data or pending_data.get('razorpay_order_id') != order_id:
            return JsonResponse({'error': 'No matching pending application'}, status=400)

        # Verify signature
        payment_settings = get_payment_settings()
        key = payment_settings.razorpay_test_key if payment_settings.test_mode else payment_settings.razorpay_key_id
        secret = payment_settings.razorpay_test_secret if payment_settings.test_mode else payment_settings.razorpay_key_secret
        client = razorpay.Client(auth=(key, secret))
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        try:
            client.utility.verify_payment_signature(params_dict)
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({'error': 'Invalid signature'}, status=400)

        # Payment verified – set payment info and create application
        pending_data['payment_method'] = 'razorpay'
        pending_data['razorpay_payment_id'] = payment_id
        request.session['pending_application'] = pending_data

        # Create the application
        return create_application_from_session(request)

    # --- Normal application (app_id > 0) ---
    app = get_object_or_404(Application, id=app_id, user=request.user)

    payment_settings = get_payment_settings()
    key = payment_settings.razorpay_test_key if payment_settings.test_mode else payment_settings.razorpay_key_id
    secret = payment_settings.razorpay_test_secret if payment_settings.test_mode else payment_settings.razorpay_key_secret

    client = razorpay.Client(auth=(key, secret))
    params_dict = {
        'razorpay_order_id': order_id,
        'razorpay_payment_id': payment_id,
        'razorpay_signature': signature
    }
    try:
        client.utility.verify_payment_signature(params_dict)
    except razorpay.errors.SignatureVerificationError:
        PaymentLog.objects.create(
            application=app,
            event_type='failed',
            amount=app.service.servicecharge_set.first().charge,
            razorpay_payment_id=payment_id,
        )
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    app.payment_status = 'paid'
    app.payment_date = timezone.now()
    app.receipt_number = app.generate_receipt_number()
    app.payment_method = 'razorpay'
    app.payment_transaction_id = payment_id
    app.save()

    PaymentLog.objects.create(
        application=app,
        event_type='captured',
        amount=app.service.servicecharge_set.first().charge,
        razorpay_payment_id=payment_id,
        razorpay_order_id=order_id,
    )

    send_payment_confirmation(app)
    return JsonResponse({
        'success': True,
        'receipt_url': reverse('download_receipt', args=[app.id])
    })


@login_required
def mark_payment_done(request, app_id):
    """Manual payment confirmation (UPI or Cash)."""
    # Check if this is a pending application (app_id == 0)
    if app_id == 0:
        pending_data = request.session.get('pending_application', None)
        if not pending_data:
            messages.error(request, _('No pending application found.'))
            return redirect('services')

        service = get_object_or_404(Service, id=pending_data['service_id'])
        payment_settings = get_payment_settings()
        method = request.POST.get('payment_method', 'upi')
        if method == 'upi' and not payment_settings.upi_enabled:
            messages.error(request, _('UPI payments are not enabled.'))
            return redirect('payment_checkout', service_id=service.id)
        if method == 'cash' and not payment_settings.cash_enabled:
            messages.error(request, _('Cash payments are not enabled.'))
            return redirect('payment_checkout', service_id=service.id)

        utr = request.POST.get('utr_number', '').strip()
        payment_app = request.POST.get('payment_app', 'upi')

        # Store payment info in session so that create_application_from_session can use it
        pending_data['payment_method'] = method
        pending_data['utr_number'] = utr
        pending_data['payment_app'] = payment_app
        request.session['pending_application'] = pending_data

        # Create the application
        return create_application_from_session(request)

    # --- Existing application (app_id > 0) ---
    application = get_object_or_404(Application, id=app_id, user=request.user)

    if application.payment_status == 'paid':
        messages.warning(request, _('Payment already processed.'))
        return redirect('application_detail', app_id=app_id)

    payment_settings = get_payment_settings()
    method = request.POST.get('payment_method', 'upi')
    if method == 'upi' and not payment_settings.upi_enabled:
        messages.error(request, _('UPI payments are not enabled.'))
        return redirect('application_detail', app_id=app_id)
    if method == 'cash' and not payment_settings.cash_enabled:
        messages.error(request, _('Cash payments are not enabled.'))
        return redirect('application_detail', app_id=app_id)

    # Anti-abuse: 24h window
    time_limit = timezone.now() - timedelta(hours=24)
    if application.created_at < time_limit:
        messages.error(request, _('Payment window expired. Please contact admin.'))
        return redirect('application_detail', app_id=app_id)

    utr = request.POST.get('utr_number', '').strip()
    payment_app = request.POST.get('payment_app', 'upi')

    application.payment_status = 'paid'
    application.payment_date = timezone.now()
    application.receipt_number = application.generate_receipt_number()
    application.payment_method = method
    application.utr_number = utr
    application.payment_app = payment_app
    application.save()

    PaymentLog.objects.create(
        application=application,
        event_type='manual_confirmed',
        amount=application.service.servicecharge_set.first().charge,
    )

    send_payment_confirmation(application)
    messages.success(request, _('Payment confirmed. Your receipt is ready.'))
    cache.delete('reports_data')
    return redirect('application_detail', app_id=app_id)


@login_required
def download_receipt(request, app_id):
    """Download receipt as PDF."""
    application = get_object_or_404(Application, id=app_id, user=request.user)
    if application.payment_status != 'paid':
        messages.error(request, _('No payment record found.'))
        return redirect('application_detail', app_id=app_id)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height-1*inch, "PAYMENT RECEIPT")
    c.setFont("Helvetica", 8)
    c.drawString(1*inch, height-1.3*inch, "System-Generated Receipt")

    # Payment details
    c.setFont("Helvetica", 12)
    y = height - 1.8*inch
    c.drawString(1*inch, y, f"Receipt No: {application.receipt_number}")
    c.drawString(1*inch, y-0.3*inch, f"Date: {application.payment_date.strftime('%d %b %Y, %H:%M')}")
    c.drawString(1*inch, y-0.6*inch, f"Transaction ID: {application.payment_transaction_id or 'N/A'}")
    c.drawString(1*inch, y-0.9*inch, f"UTR: {application.utr_number or 'N/A'}")
    c.drawString(1*inch, y-1.2*inch, f"Payment App: {application.get_payment_app_display() or 'N/A'}")
    c.drawString(1*inch, y-1.5*inch, f"Payment Method: {application.get_payment_method_display()}")

    # Customer details
    c.drawString(1*inch, y-2.0*inch, "Customer Details")
    c.drawString(1*inch, y-2.3*inch, f"Name: {application.full_name}")
    c.drawString(1*inch, y-2.6*inch, f"Phone: {application.phone}")
    c.drawString(1*inch, y-2.9*inch, f"Email: {application.email}")

    # Service details
    c.drawString(1*inch, y-3.4*inch, "Service Details")
    c.drawString(1*inch, y-3.7*inch, f"Service: {application.service.name}")
    charge = application.service.servicecharge_set.first().charge if application.service.servicecharge_set.exists() else 0
    c.drawString(1*inch, y-4.0*inch, f"Amount: ₹{charge}")

    # Footer
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(1*inch, 0.5*inch, "Thank you for your payment. This is a system-generated receipt.")
    c.drawString(1*inch, 0.3*inch, f"Verified on: {timezone.now().strftime('%d %b %Y %H:%M:%S')}")

    c.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"receipt_{application.receipt_number}.pdf")


@csrf_exempt
def razorpay_webhook(request):
    """Handle Razorpay webhook for payment confirmation."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', None)
        if webhook_secret:
            from razorpay.utility import verify_webhook_signature
            signature = request.headers.get('X-Razorpay-Signature')
            if not signature:
                return JsonResponse({'status': 'missing signature'}, status=400)
            verify_webhook_signature(request.body, signature, webhook_secret)

        payload = json.loads(request.body)
        event = payload.get('event')

        if event == 'payment.captured':
            payment_id = payload['payload']['payment']['entity']['id']
            order_id = payload['payload']['payment']['entity']['order_id']
            amount = payload['payload']['payment']['entity']['amount'] / 100

            app = Application.objects.filter(payment_transaction_id=order_id).first()
            if app and app.payment_status == 'pending':
                app.payment_status = 'paid'
                app.payment_date = timezone.now()
                app.receipt_number = app.generate_receipt_number()
                app.payment_method = 'razorpay'
                app.payment_transaction_id = payment_id
                app.save()

                PaymentLog.objects.create(
                    application=app,
                    event_type='webhook_received',
                    amount=amount,
                    razorpay_payment_id=payment_id,
                    razorpay_order_id=order_id,
                    webhook_data=payload,
                )

                send_payment_confirmation(app)
                return JsonResponse({'status': 'success'})
            else:
                logger.info(f"Webhook: application not found or already paid: {order_id}")
                return JsonResponse({'status': 'ignored'})

        elif event == 'payment.failed':
            order_id = payload['payload']['payment']['entity']['order_id']
            app = Application.objects.filter(payment_transaction_id=order_id).first()
            if app:
                app.payment_status = 'failed'
                app.save()
                PaymentLog.objects.create(
                    application=app,
                    event_type='failed',
                    amount=0,
                    razorpay_order_id=order_id,
                    webhook_data=payload,
                )

        return JsonResponse({'status': 'ignored'})

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JsonResponse({'status': 'error'}, status=500)


# =============================================================================
# DASHBOARD REPORT
# =============================================================================

@login_required
@user_passes_test(is_admin)
def reports_dashboard(request):
    cache_key = 'reports_data'
    data = cache.get(cache_key)
    if not data:
        app_status_counts = Application.objects.values('status').annotate(count=Count('id'))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        daily_apps = Application.objects.filter(created_at__date__gte=start_date) \
            .annotate(day=TruncDate('created_at')) \
            .values('day') \
            .annotate(count=Count('id')) \
            .order_by('day')
        appt_status_counts = Appointment.objects.values('status').annotate(count=Count('id'))
        weekly_users = User.objects.filter(date_joined__gte=timezone.now() - timedelta(days=90)) \
            .annotate(week=ExtractWeek('date_joined')) \
            .values('week') \
            .annotate(count=Count('id')) \
            .order_by('week')
        payment_status_counts = Application.objects.values('payment_status').annotate(count=Count('id'))

        data = {
            'app_status': list(app_status_counts),
            'daily_apps': list(daily_apps),
            'appt_status': list(appt_status_counts),
            'weekly_users': list(weekly_users),
            'payment_status': list(payment_status_counts),
        }
        cache.set(cache_key, data, 60*60)

    context = {
        'data': data,
        'business': get_business(),
    }
    return render(request, 'reports_dashboard.html', context)


# Alias to maintain backward compatibility
create_payment = create_razorpay_order
