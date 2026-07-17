# =============================================================================
# IMPORTS
# =============================================================================
import os
import tempfile
from .models import Application, DocumentUpload
from .forms import ApplicationForm, DocumentUploadForm
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from pypdf import PdfReader, PdfWriter
from .models import DocumentUpload
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.forms import formset_factory
from django.contrib import messages
from .forms import ApplicationForm, DocumentUploadForm
from .models import Service, RequiredDocument, Application, DocumentUpload
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.db import OperationalError  # <-- added for safe DB access
from django.utils.translation import gettext_lazy as _
from .forms import (
    ServiceForm, AnnouncementForm, JobNotificationForm,
    GovernmentSchemeForm, AppointmentForm, ContactFormDashboard,
    DownloadFormForm, ServiceChargeForm, GalleryForm, BusinessInfoForm,
    AppointmentFormDashboard   # <-- added for admin dashboard
)
from .models import (
    Review, Announcement, Gallery, Service, ServiceCharge,
    DownloadForm, GovernmentScheme, JobNotification, FAQ,
    BusinessInfo, RequiredDocument, Appointment, Contact  # <-- added RequiredDocument
)
from .forms import (
    ContactForm, AppointmentForm, ReviewForm,
    CustomUserCreationForm, ProfileUpdateForm,
)
from django.contrib.auth import get_user_model
from .forms import RequiredDocumentForm
from .models import RequiredDocument

User = get_user_model()

# =============================================================================
# HELPERS / CONTEXT
# =============================================================================

def get_business():
    """Return the first (and only) BusinessInfo instance, with safe DB access."""
    try:
        return BusinessInfo.objects.first()
    except OperationalError:
        return None


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form, 'business': get_business()})


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, 'profile.html', {'form': form, 'business': get_business()})


# =============================================================================
# ROLE CHECKS
# =============================================================================

def is_admin(user):
    return user.is_authenticated and user.role in ('admin', 'superadmin')


def is_superadmin(user):
    return user.is_authenticated and user.role == 'superadmin'


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Fetch all data
    services = Service.objects.all().order_by('name')
    appointments = Appointment.objects.all().order_by('-appointment_date')
    contacts = Contact.objects.all().order_by('-created_at')
    announcements = Announcement.objects.all().order_by('-created_at')
    jobs = JobNotification.objects.all().order_by('-last_date')
    schemes = GovernmentScheme.objects.all().order_by('-last_date')
    forms_list = DownloadForm.objects.all().order_by('-uploaded_at')
    servicecharges = ServiceCharge.objects.select_related('service').all()   # <-- new
    gallery_images = Gallery.objects.all()                                  # <-- new
    business_info = BusinessInfo.objects.first()                            # <-- new
    applications = Application.objects.all().order_by('-created_at')

    # Initialize empty forms for each model
    service_form = ServiceForm()
    announcement_form = AnnouncementForm()
    job_form = JobNotificationForm()
    scheme_form = GovernmentSchemeForm()
    appointment_form = AppointmentFormDashboard()      # <-- changed to AppointmentFormDashboard
    contact_form = ContactFormDashboard()
    download_form = DownloadFormForm()
    servicecharge_form = ServiceChargeForm()      # <-- new
    gallery_form = GalleryForm()                  # <-- new
    businessinfo_form = BusinessInfoForm(instance=business_info)  # <-- new
    required_docs = RequiredDocument.objects.select_related('service').all().order_by('service__name')
    required_doc_form = RequiredDocumentForm()

    # Handle POST actions
    if request.method == 'POST':
        action = request.POST.get('action')
        model_type = request.POST.get('model_type')
        obj_id = request.POST.get('id')

        if action == 'add':
            if model_type == 'service':
                form = ServiceForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Service added.')
                else:
                    messages.error(request, 'Error adding service. Check fields.')
            elif model_type == 'requireddoc':
                form = RequiredDocumentForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Required document added.')
                else:
                    messages.error(request, 'Error adding required document. Check fields.')
            elif model_type == 'announcement':
                form = AnnouncementForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Announcement added.')
                else:
                    messages.error(request, 'Error adding announcement.')
            elif model_type == 'job':
                form = JobNotificationForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Job notification added.')
                else:
                    messages.error(request, 'Error adding job.')
            elif model_type == 'scheme':
                # FIX: include request.FILES for image upload
                form = GovernmentSchemeForm(request.POST, request.FILES)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Scheme added.')
                else:
                    messages.error(request, 'Error adding scheme.')
            elif model_type == 'appointment':
                # FIX: use AppointmentFormDashboard which includes status field
                form = AppointmentFormDashboard(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Appointment added.')
                else:
                    messages.error(request, 'Error adding appointment.')
            elif model_type == 'contact':
                form = ContactFormDashboard(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Contact added.')
                else:
                    messages.error(request, 'Error adding contact.')
            elif model_type == 'form':
                form = DownloadFormForm(request.POST, request.FILES)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Download form uploaded.')
                else:
                    messages.error(request, 'Error uploading form.')
            elif model_type == 'servicecharge':
                form = ServiceChargeForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Service charge added.')
                else:
                    messages.error(request, 'Error adding service charge.')
            elif model_type == 'gallery':
                form = GalleryForm(request.POST, request.FILES)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Gallery image uploaded.')
                else:
                    messages.error(request, 'Error uploading gallery image.')
            return redirect('admin_dashboard')

        elif action == 'edit':
            if model_type == 'service' and obj_id:
                instance = get_object_or_404(Service, id=obj_id)
                form = ServiceForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Service updated.')
                else:
                    messages.error(request, 'Error updating service.')
            elif model_type == 'requireddoc' and obj_id:
                instance = get_object_or_404(RequiredDocument, id=obj_id)
                form = RequiredDocumentForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Required document updated.')
                else:
                    messages.error(request, 'Error updating required document.')
            elif model_type == 'announcement' and obj_id:
                instance = get_object_or_404(Announcement, id=obj_id)
                form = AnnouncementForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Announcement updated.')
                else:
                    messages.error(request, 'Error updating announcement.')
            elif model_type == 'job' and obj_id:
                instance = get_object_or_404(JobNotification, id=obj_id)
                form = JobNotificationForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Job updated.')
                else:
                    messages.error(request, 'Error updating job.')
            elif model_type == 'scheme' and obj_id:
                # FIX: include request.FILES for image upload
                instance = get_object_or_404(GovernmentScheme, id=obj_id)
                form = GovernmentSchemeForm(request.POST, request.FILES, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Scheme updated.')
                else:
                    messages.error(request, 'Error updating scheme.')
            elif model_type == 'appointment' and obj_id:
                # FIX: use AppointmentFormDashboard for editing
                instance = get_object_or_404(Appointment, id=obj_id)
                form = AppointmentFormDashboard(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Appointment updated.')
                else:
                    messages.error(request, 'Error updating appointment.')
            elif model_type == 'contact' and obj_id:
                instance = get_object_or_404(Contact, id=obj_id)
                # FIX: handle reply separately, if present
                if 'reply' in request.POST:
                    instance.reply = request.POST.get('reply')
                    instance.replied = True
                    instance.save()
                    messages.success(request, 'Reply saved.')
                else:
                    form = ContactFormDashboard(request.POST, instance=instance)
                    if form.is_valid():
                        form.save()
                        messages.success(request, 'Contact updated.')
                    else:
                        messages.error(request, 'Error updating contact.')
            elif model_type == 'form' and obj_id:
                instance = get_object_or_404(DownloadForm, id=obj_id)
                form = DownloadFormForm(request.POST, request.FILES, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Form updated.')
                else:
                    messages.error(request, 'Error updating form.')
            elif model_type == 'servicecharge' and obj_id:
                instance = get_object_or_404(ServiceCharge, id=obj_id)
                form = ServiceChargeForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Service charge updated.')
                else:
                    messages.error(request, 'Error updating service charge.')
            elif model_type == 'businessinfo' and obj_id:
                instance = get_object_or_404(BusinessInfo, id=obj_id)
                form = BusinessInfoForm(request.POST, request.FILES, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Business info updated.')
                else:
                    messages.error(request, 'Error updating business info.')
            return redirect('admin_dashboard')

        elif action == 'delete':
            if model_type == 'service' and obj_id:
                get_object_or_404(Service, id=obj_id).delete()
                messages.success(request, 'Service deleted.')
            elif model_type == 'announcement' and obj_id:
                get_object_or_404(Announcement, id=obj_id).delete()
                messages.success(request, 'Announcement deleted.')
            elif model_type == 'requireddoc' and obj_id:
                get_object_or_404(RequiredDocument, id=obj_id).delete()
                messages.success(request, 'Required document deleted.')  
            elif model_type == 'job' and obj_id:
                get_object_or_404(JobNotification, id=obj_id).delete()
                messages.success(request, 'Job deleted.')
            elif model_type == 'scheme' and obj_id:
                get_object_or_404(GovernmentScheme, id=obj_id).delete()
                messages.success(request, 'Scheme deleted.')
            elif model_type == 'appointment' and obj_id:
                get_object_or_404(Appointment, id=obj_id).delete()
                messages.success(request, 'Appointment deleted.')
            elif model_type == 'contact' and obj_id:
                get_object_or_404(Contact, id=obj_id).delete()
                messages.success(request, 'Contact deleted.')
            elif model_type == 'form' and obj_id:
                get_object_or_404(DownloadForm, id=obj_id).delete()
                messages.success(request, 'Form deleted.')
            elif model_type == 'servicecharge' and obj_id:
                get_object_or_404(ServiceCharge, id=obj_id).delete()
                messages.success(request, 'Service charge deleted.')
            elif model_type == 'gallery' and obj_id:
                get_object_or_404(Gallery, id=obj_id).delete()
                messages.success(request, 'Gallery image deleted.')
            return redirect('admin_dashboard')

    context = {
        'services': services,
        'appointments': appointments,
        'contacts': contacts,
        'announcements': announcements,
        'jobs': jobs,
        'schemes': schemes,
        'forms_list': forms_list,
        'servicecharges': servicecharges,
        'gallery_images': gallery_images,
        'business_info': business_info,
        'service_form': service_form,
        'announcement_form': announcement_form,
        'job_form': job_form,
        'scheme_form': scheme_form,
        'appointment_form': appointment_form,
        'contact_form': contact_form,
        'download_form': download_form,
        'servicecharge_form': servicecharge_form,
        'gallery_form': gallery_form,
        'businessinfo_form': businessinfo_form,
        'applications': applications,
        'required_docs': required_docs,
        'required_doc_form': required_doc_form,
        'business': get_business(),
    }
    return render(request, 'admindashboard.html', context)


@login_required
@user_passes_test(is_superadmin)
def superadmin_dashboard(request):
    # Fetch all data (same as admin, plus users)
    services = Service.objects.all().order_by('name')
    appointments = Appointment.objects.all().order_by('-appointment_date')
    contacts = Contact.objects.all().order_by('-created_at')
    announcements = Announcement.objects.all().order_by('-created_at')
    jobs = JobNotification.objects.all().order_by('-last_date')
    schemes = GovernmentScheme.objects.all().order_by('-last_date')
    forms_list = DownloadForm.objects.all().order_by('-uploaded_at')
    users = User.objects.all().order_by('username')
    servicecharges = ServiceCharge.objects.select_related('service').all()
    gallery_images = Gallery.objects.all()
    business_info = BusinessInfo.objects.first()
    applications = Application.objects.all().order_by('-created_at')

    # Initialize forms
    service_form = ServiceForm()
    announcement_form = AnnouncementForm()
    job_form = JobNotificationForm()
    scheme_form = GovernmentSchemeForm()
    appointment_form = AppointmentFormDashboard()      # <-- changed to AppointmentFormDashboard
    contact_form = ContactFormDashboard()
    download_form = DownloadFormForm()
    servicecharge_form = ServiceChargeForm()
    gallery_form = GalleryForm()
    businessinfo_form = BusinessInfoForm(instance=business_info)
    required_docs = RequiredDocument.objects.select_related('service').all().order_by('service__name')
    required_doc_form = RequiredDocumentForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        model_type = request.POST.get('model_type')
        obj_id = request.POST.get('id')

        # ---- ADD ----
        if action == 'add':
            if model_type == 'service':
                form = ServiceForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Service added.')
                else:
                    messages.error(request, 'Error adding service.')
            elif model_type == 'requireddoc':
                form = RequiredDocumentForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Required document added.')
                else:
                    messages.error(request, 'Error adding required document. Check fields.')
            elif model_type == 'announcement':
                form = AnnouncementForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Announcement added.')
                else:
                    messages.error(request, 'Error adding announcement.')
            elif model_type == 'job':
                form = JobNotificationForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Job notification added.')
                else:
                    messages.error(request, 'Error adding job.')
            elif model_type == 'scheme':
                # FIX: include request.FILES for image upload
                form = GovernmentSchemeForm(request.POST, request.FILES)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Scheme added.')
                else:
                    messages.error(request, 'Error adding scheme.')
            elif model_type == 'appointment':
                # FIX: use AppointmentFormDashboard
                form = AppointmentFormDashboard(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Appointment added.')
                else:
                    messages.error(request, 'Error adding appointment.')
            elif model_type == 'contact':
                form = ContactFormDashboard(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Contact added.')
                else:
                    messages.error(request, 'Error adding contact.')
            elif model_type == 'form':
                form = DownloadFormForm(request.POST, request.FILES)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Download form uploaded.')
                else:
                    messages.error(request, 'Error uploading form.')
            elif model_type == 'servicecharge':
                form = ServiceChargeForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Service charge added.')
                else:
                    messages.error(request, 'Error adding service charge.')
            elif model_type == 'gallery':
                form = GalleryForm(request.POST, request.FILES)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Gallery image uploaded.')
                else:
                    messages.error(request, 'Error uploading gallery image.')
            return redirect('superadmin_dashboard')

        # ---- EDIT ----
        elif action == 'edit':
            if model_type == 'service' and obj_id:
                instance = get_object_or_404(Service, id=obj_id)
                form = ServiceForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Service updated.')
                else:
                    messages.error(request, 'Error updating service.')
            elif model_type == 'announcement' and obj_id:
                instance = get_object_or_404(Announcement, id=obj_id)
                form = AnnouncementForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Announcement updated.')
                else:
                    messages.error(request, 'Error updating announcement.')
            elif model_type == 'requireddoc' and obj_id:
                instance = get_object_or_404(RequiredDocument, id=obj_id)
                form = RequiredDocumentForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Required document updated.')
                else:
                    messages.error(request, 'Error updating required document.')
            elif model_type == 'job' and obj_id:
                instance = get_object_or_404(JobNotification, id=obj_id)
                form = JobNotificationForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Job updated.')
                else:
                    messages.error(request, 'Error updating job.')
            elif model_type == 'scheme' and obj_id:
                # FIX: include request.FILES for image upload
                instance = get_object_or_404(GovernmentScheme, id=obj_id)
                form = GovernmentSchemeForm(request.POST, request.FILES, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Scheme updated.')
                else:
                    messages.error(request, 'Error updating scheme.')
            elif model_type == 'appointment' and obj_id:
                # FIX: use AppointmentFormDashboard for editing
                instance = get_object_or_404(Appointment, id=obj_id)
                form = AppointmentFormDashboard(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Appointment updated.')
                else:
                    messages.error(request, 'Error updating appointment.')
            elif model_type == 'contact' and obj_id:
                instance = get_object_or_404(Contact, id=obj_id)
                # FIX: handle reply separately, if present
                if 'reply' in request.POST:
                    instance.reply = request.POST.get('reply')
                    instance.replied = True
                    instance.save()
                    messages.success(request, 'Reply saved.')
                else:
                    form = ContactFormDashboard(request.POST, instance=instance)
                    if form.is_valid():
                        form.save()
                        messages.success(request, 'Contact updated.')
                    else:
                        messages.error(request, 'Error updating contact.')
            elif model_type == 'form' and obj_id:
                instance = get_object_or_404(DownloadForm, id=obj_id)
                form = DownloadFormForm(request.POST, request.FILES, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Form updated.')
                else:
                    messages.error(request, 'Error updating form.')
            elif model_type == 'servicecharge' and obj_id:
                instance = get_object_or_404(ServiceCharge, id=obj_id)
                form = ServiceChargeForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Service charge updated.')
                else:
                    messages.error(request, 'Error updating service charge.')
            elif model_type == 'businessinfo' and obj_id:
                instance = get_object_or_404(BusinessInfo, id=obj_id)
                form = BusinessInfoForm(request.POST, request.FILES, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Business info updated.')
                else:
                    messages.error(request, 'Error updating business info.')
            return redirect('superadmin_dashboard')

        # ---- DELETE ----
        elif action == 'delete':
            if model_type == 'service' and obj_id:
                get_object_or_404(Service, id=obj_id).delete()
                messages.success(request, 'Service deleted.')
            elif model_type == 'announcement' and obj_id:
                get_object_or_404(Announcement, id=obj_id).delete()
                messages.success(request, 'Announcement deleted.')
            elif model_type == 'requireddoc' and obj_id:
                get_object_or_404(RequiredDocument, id=obj_id).delete()
                messages.success(request, 'Required document deleted.')
            elif model_type == 'job' and obj_id:
                get_object_or_404(JobNotification, id=obj_id).delete()
                messages.success(request, 'Job deleted.')
            elif model_type == 'scheme' and obj_id:
                get_object_or_404(GovernmentScheme, id=obj_id).delete()
                messages.success(request, 'Scheme deleted.')
            elif model_type == 'appointment' and obj_id:
                get_object_or_404(Appointment, id=obj_id).delete()
                messages.success(request, 'Appointment deleted.')
            elif model_type == 'contact' and obj_id:
                get_object_or_404(Contact, id=obj_id).delete()
                messages.success(request, 'Contact deleted.')
            elif model_type == 'form' and obj_id:
                get_object_or_404(DownloadForm, id=obj_id).delete()
                messages.success(request, 'Form deleted.')
            elif model_type == 'servicecharge' and obj_id:
                get_object_or_404(ServiceCharge, id=obj_id).delete()
                messages.success(request, 'Service charge deleted.')
            elif model_type == 'gallery' and obj_id:
                get_object_or_404(Gallery, id=obj_id).delete()
                messages.success(request, 'Gallery image deleted.')
            return redirect('superadmin_dashboard')

        # ---- USER ROLE UPDATE (superadmin only) ----
        elif action == 'edit_user':
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('new_role')
            if user_id and new_role:
                user = get_object_or_404(User, id=user_id)
                user.role = new_role
                user.save()
                messages.success(request, f"User {user.username} role updated to {new_role}.")
            return redirect('superadmin_dashboard')

    context = {
        'services': services,
        'appointments': appointments,
        'contacts': contacts,
        'announcements': announcements,
        'jobs': jobs,
        'schemes': schemes,
        'forms_list': forms_list,
        'users': users,
        'servicecharges': servicecharges,
        'gallery_images': gallery_images,
        'business_info': business_info,
        'service_form': service_form,
        'announcement_form': announcement_form,
        'job_form': job_form,
        'scheme_form': scheme_form,
        'appointment_form': appointment_form,
        'contact_form': contact_form,
        'download_form': download_form,
        'servicecharge_form': servicecharge_form,
        'gallery_form': gallery_form,
        'businessinfo_form': businessinfo_form,
        'applications': applications,
        'required_docs': required_docs,
        'required_doc_form': required_doc_form,
        'business': get_business(),
    }
    return render(request, 'superadmindashboard.html', context)


# =============================================================================
# PUBLIC VIEWS
# =============================================================================

def home(request):
    context = {
        'business': get_business(),
        'services': Service.objects.filter(active=True)[:8],
        'announcements': Announcement.objects.all()[:5],
        'reviews': Review.objects.filter(approved=True)[:6],
        'gallery': Gallery.objects.all()[:8],
        'charges': ServiceCharge.objects.select_related('service').all()[:3],
    }
    return render(request, 'homepage.html', context)

def about(request):
    context = {
        'business': get_business(),
        'services': Service.objects.filter(active=True),
        'charges': ServiceCharge.objects.select_related('service').all(),
    }
    return render(request, 'aboutus.html', context)

def services(request):
    context = {
        'business': get_business(),
        'services': Service.objects.filter(active=True),
    }
    return render(request, 'services.html', context)


def gallery(request):
    images = Gallery.objects.all().order_by('-id')
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
            contact_instance = form.save()

            # Send email notification
            try:
                send_mail(
                    subject=f'New Contact Message from {contact_instance.name}',
                    message=(
                        f'Name: {contact_instance.name}\n'
                        f'Email: {contact_instance.email}\n'
                        f'Phone: {contact_instance.phone}\n'
                        f'Message:\n{contact_instance.message}'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_EMAIL],
                    fail_silently=True,
                )
            except Exception:
                pass

            messages.success(request, 'Your message has been sent successfully.')
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
            form.save()
            messages.success(request, 'Appointment booked successfully.')
            return redirect('appointment')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AppointmentForm()

    return render(request, 'appointment.html', {
        'business': get_business(),
        'form': form,
        'services': Service.objects.filter(active=True),
    })


def faq(request):
    return render(request, 'faq.html', {
        'business': get_business(),
        'faqs': FAQ.objects.all(),
    })


def documents(request):
    """
    Display a flat list of required documents with pagination.
    """
    documents_qs = RequiredDocument.objects.select_related('service').all().order_by('service__name', 'document_name')
    paginator = Paginator(documents_qs, 20)   # 20 per page
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
    return render(request, 'download_forms.html', {
        'business': get_business(),
        'forms': DownloadForm.objects.all(),
    })


def charges(request):
    return render(request, 'service_charges.html', {
        'business': get_business(),
        'charges': ServiceCharge.objects.select_related('service'),
    })


def reviews(request):
    all_reviews = Review.objects.filter(approved=True).order_by('-created_at')
    paginator = Paginator(all_reviews, 10)
    page = request.GET.get('page')

    try:
        reviews_page = paginator.page(page)
    except PageNotAnInteger:
        reviews_page = paginator.page(1)
    except EmptyPage:
        reviews_page = paginator.page(paginator.num_pages)

    return render(request, 'customer_reviews.html', {
        'business': get_business(),
        'reviews': reviews_page,
        'form': ReviewForm(),
    })


def submit_review(request):
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.approved = False
            review.save()
            messages.success(
                request,
                'Thank you! Your review will appear after admin approval.'
            )
        else:
            messages.error(request, 'Please correct the errors in the review form.')
    return redirect('reviews')


def announcements(request):
    announcements_qs = Announcement.objects.all().order_by('-created_at')
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
    schemes_qs = GovernmentScheme.objects.all().order_by('-last_date')
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
    jobs_qs = JobNotification.objects.order_by('last_date')
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

@login_required
def apply_service(request, service_id):
    service = get_object_or_404(Service, id=service_id, active=True)
    required_docs = RequiredDocument.objects.filter(service=service)

    # Pre-fill user data if already exists
    initial_data = {
        'full_name': request.user.get_full_name() or request.user.username,
        'phone': request.user.phone or '',
        'email': request.user.email,
        'address': request.user.address or '',
    }

    if request.method == 'POST':
        form = ApplicationForm(request.POST)
        # We'll create a formset for documents
        DocumentFormSet = formset_factory(DocumentUploadForm, extra=len(required_docs), max_num=len(required_docs))
        formset = DocumentFormSet(request.POST, request.FILES)

        if form.is_valid() and formset.is_valid():
            # Save application
            application = form.save(commit=False)
            application.user = request.user
            application.service = service
            application.save()

            # Save each document
            for i, doc_form in enumerate(formset.cleaned_data):
                if doc_form:  # ensure not empty
                    doc_name = required_docs[i].document_name if i < len(required_docs) else 'Other'
                    DocumentUpload.objects.create(
                        application=application,
                        document_name=doc_name,
                        file=doc_form['file'],
                        is_mandatory=True,  # we treat all as mandatory for simplicity
                    )

            messages.success(request, _('Your application has been submitted successfully.'))
            return redirect('my_applications')
        else:
            messages.error(request, _('Please correct the errors below.'))
    else:
        form = ApplicationForm(initial=initial_data)
        # Pre-populate formset with document names
        DocumentFormSet = formset_factory(DocumentUploadForm, extra=len(required_docs), max_num=len(required_docs))
        initial_docs = [{'document_name': doc.document_name} for doc in required_docs]
        formset = DocumentFormSet(initial=initial_docs)

    context = {
        'service': service,
        'required_docs': required_docs,
        'form': form,
        'formset': formset,
        'business': get_business(),
    }
    return render(request, 'apply_service.html', context)

@login_required
def my_applications(request):
    applications = Application.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'my_applications.html', {
        'applications': applications,
        'business': get_business(),
    })
    
@login_required
def application_detail(request, app_id):
    application = get_object_or_404(Application, id=app_id, user=request.user)
    documents = application.documents.all()
    return render(request, 'application_detail.html', {
        'application': application,
        'documents': documents,
        'business': get_business(),
    })
    
from django.http import JsonResponse

@login_required
@user_passes_test(is_admin)
def application_detail_ajax(request, app_id):
    app = get_object_or_404(Application, id=app_id)
    documents = app.documents.all()
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
    application = get_object_or_404(Application, id=app_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # --- Update Status ---
        if action == 'update_status':
            new_status = request.POST.get('status')
            if new_status in dict(Application.STATUS_CHOICES):
                application.status = new_status
                application.save()
                messages.success(request, _("Status updated successfully."))
            else:
                messages.error(request, _("Invalid status."))
            return redirect('application_admin_detail', app_id=app_id)
        
        # --- Delete Document ---
        elif action == 'delete_document':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(DocumentUpload, id=doc_id, application=application)
            doc.delete()
            messages.success(request, _("Document deleted."))
            return redirect('application_admin_detail', app_id=app_id)
        
        
        # --- Add Document ---
        elif action == 'add_document':
            doc_name = request.POST.get('document_name')
            file = request.FILES.get('file')
            if doc_name and file:
                DocumentUpload.objects.create(
                    application=application,
                    document_name=doc_name,
                    file=file,
                    is_mandatory=False  # optional
                )
                messages.success(request, _("Document uploaded."))
            else:
                messages.error(request, _("Please provide both name and file."))
            return redirect('application_admin_detail', app_id=app_id)
        
        # --- Verify / Unverify Document ---
        elif action == 'verify_document':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(DocumentUpload, id=doc_id, application=application)
            doc.verified = not doc.verified   # toggle
            doc.save()
            messages.success(request, _("Document verification toggled."))
            return redirect('application_admin_detail', app_id=app_id)
    
    # GET – show the form
    documents = application.documents.all()
    context = {
        'application': application,
        'documents': documents,
        'business': get_business(),
    }
    return render(request, 'application_admin_detail.html', context)


@login_required
@user_passes_test(is_admin)
def split_pdf(request, pk):
    document = get_object_or_404(DocumentUpload, pk=pk)

    if request.method == "POST":

        pages = request.POST.get("pages")

        reader = PdfReader(document.file)
        writer = PdfWriter()

        total_pages = len(reader.pages)

        try:
            selected_pages = []

            parts = pages.split(",")

            for part in parts:
                part = part.strip()

                if "-" in part:
                    start, end = part.split("-")
                    start = int(start)
                    end = int(end)

                    for p in range(start, end + 1):
                        selected_pages.append(p)

                else:
                    selected_pages.append(int(part))

            for page in selected_pages:

                if page < 1 or page > total_pages:
                    raise Exception("Invalid page")

                writer.add_page(reader.pages[page - 1])

            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

            with open(temp.name, "wb") as output:
                writer.write(output)

            return FileResponse(
                open(temp.name, "rb"),
                as_attachment=True,
                filename=f"split_{os.path.basename(document.file.name)}",
            )

        except Exception:
            return render(
                request,
                "split_pdf.html",
                {
                    "document": document,
                    "error": "Invalid page numbers.",
                },
            )

    return render(
        request,
        "split_pdf.html",
        {
            "document": document,
        },
    )