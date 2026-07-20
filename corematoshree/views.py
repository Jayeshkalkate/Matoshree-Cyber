# =============================================================================
# IMPORTS
# =============================================================================
import os
import tempfile
import logging
from django.contrib import messages
from django.db import models
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import OperationalError
from django.forms import formset_factory
from django.http import FileResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from pypdf import PdfReader, PdfWriter
from django.core.cache import cache
from django.db import ProgrammingError
from .models import (
    User, Contact, Appointment, Review, Service, Announcement,
    JobNotification, GovernmentScheme, DownloadForm, ServiceCharge,
    Gallery, BusinessInfo, RequiredDocument, FAQ, Application, DocumentUpload
)
from .forms import (
    CustomUserCreationForm, ProfileUpdateForm,
    ContactForm, AppointmentForm, ReviewForm,
    ServiceForm, AnnouncementForm, JobNotificationForm,
    GovernmentSchemeForm, AppointmentFormDashboard,
    ContactFormDashboard, DownloadFormForm, ServiceChargeForm,
    GalleryForm, BusinessInfoForm, RequiredDocumentForm,
    ApplicationForm, DocumentUploadForm
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

def is_admin(user):
    return user.is_authenticated and user.role in ('admin', 'superadmin')

def is_superadmin(user):
    return user.is_authenticated and user.role == 'superadmin'

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


# =============================================================================
# DASHBOARD (ADMIN & SUPERADMIN) – with caching
# =============================================================================

DASHBOARD_CACHE_KEY = 'dashboard_data_v2'   # single source of truth

def _get_dashboard_common_data():
    cache_key = DASHBOARD_CACHE_KEY
    cached = cache.get(cache_key)

    if cached is not None:
        # cached contains only querysets and business_info
        data = {
            'services': cached['services'],
            'appointments': cached['appointments'],
            'contacts': cached['contacts'],
            'announcements': cached['announcements'],
            'jobs': cached['jobs'],
            'schemes': cached['schemes'],
            'forms_list': cached['forms_list'],
            'servicecharges': cached['servicecharges'],
            'gallery_images': cached['gallery_images'],
            'business_info': cached['business_info'],
            'applications': cached['applications'],
            'required_docs': cached['required_docs'],
        }
    else:
        # Fetch all querysets (no forms)
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
        }
        # Cache only the querysets / business_info (forms are excluded)
        cache.set(cache_key, data, 60 * 5)

    # Add fresh form instances (never cached)
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
    })
    return data

def _handle_dashboard_post(request, is_super=False):
    """Process POST requests for admin/superadmin dashboards."""
    action = request.POST.get('action')
    model_type = request.POST.get('model_type')
    obj_id = request.POST.get('id')

    if action == 'add':
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
                return redirect('superadmin_dashboard' if is_super else 'admin_dashboard')

            # Split by comma, strip whitespace, remove empty strings
            doc_names = [name.strip() for name in raw_docs.split(',') if name.strip()]
            if not doc_names:
                messages.error(request, _('Please enter at least one document name.'))
                return redirect('superadmin_dashboard' if is_super else 'admin_dashboard')

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
            # Clear cache so dashboard shows new documents immediately
            cache.delete(DASHBOARD_CACHE_KEY)
            return redirect('superadmin_dashboard' if is_super else 'admin_dashboard')

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

        # Clear cache after any add operation (if not already cleared)
        cache.delete(DASHBOARD_CACHE_KEY)
        return redirect('superadmin_dashboard' if is_super else 'admin_dashboard')

    elif action == 'edit':
        if model_type == 'service' and obj_id:
            instance = get_object_or_404(Service, id=obj_id)
            form = ServiceForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, _('Service updated.'))
            else:
                messages.error(request, _('Error updating service.'))

        elif model_type == 'requireddoc' and obj_id:
            instance = get_object_or_404(RequiredDocument, id=obj_id)
            form = RequiredDocumentForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, _('Required document updated.'))
            else:
                messages.error(request, _('Error updating required document.'))

        elif model_type == 'announcement' and obj_id:
            instance = get_object_or_404(Announcement, id=obj_id)
            form = AnnouncementForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, _('Announcement updated.'))
            else:
                messages.error(request, _('Error updating announcement.'))

        elif model_type == 'job' and obj_id:
            instance = get_object_or_404(JobNotification, id=obj_id)
            form = JobNotificationForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, _('Job updated.'))
            else:
                messages.error(request, _('Error updating job.'))

        elif model_type == 'scheme' and obj_id:
            instance = get_object_or_404(GovernmentScheme, id=obj_id)
            form = GovernmentSchemeForm(request.POST, request.FILES, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, _('Scheme updated.'))
            else:
                messages.error(request, _('Error updating scheme.'))

        elif model_type == 'appointment' and obj_id:
            instance = get_object_or_404(Appointment, id=obj_id)
            form = AppointmentFormDashboard(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, _('Appointment updated.'))
            else:
                messages.error(request, _('Error updating appointment.'))

        elif model_type == 'contact' and obj_id:
            instance = get_object_or_404(Contact, id=obj_id)
            if 'reply' in request.POST:
                instance.reply = request.POST.get('reply')
                instance.replied = True
                instance.save()
                messages.success(request, _('Reply saved.'))
            else:
                form = ContactFormDashboard(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, _('Contact updated.'))
                else:
                    messages.error(request, _('Error updating contact.'))

        elif model_type == 'form' and obj_id:
            instance = get_object_or_404(DownloadForm, id=obj_id)
            form = DownloadFormForm(request.POST, request.FILES, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, _('Form updated.'))
            else:
                messages.error(request, _('Error updating form.'))

        elif model_type == 'servicecharge' and obj_id:
            instance = get_object_or_404(ServiceCharge, id=obj_id)
            form = ServiceChargeForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, _('Service charge updated.'))
            else:
                messages.error(request, _('Error updating service charge.'))

        elif model_type == 'businessinfo' and obj_id:
            instance = get_object_or_404(BusinessInfo, id=obj_id)
            form = BusinessInfoForm(request.POST, request.FILES, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, _('Business info updated.'))
            else:
                messages.error(request, _('Error updating business info.'))

        cache.delete(DASHBOARD_CACHE_KEY)
        cache.delete('business_info')
        return redirect('superadmin_dashboard' if is_super else 'admin_dashboard')

    elif action == 'delete':
        if model_type == 'service' and obj_id:
            get_object_or_404(Service, id=obj_id).delete()
            messages.success(request, _('Service deleted.'))
        elif model_type == 'announcement' and obj_id:
            get_object_or_404(Announcement, id=obj_id).delete()
            messages.success(request, _('Announcement deleted.'))
        elif model_type == 'requireddoc' and obj_id:
            get_object_or_404(RequiredDocument, id=obj_id).delete()
            messages.success(request, _('Required document deleted.'))
        elif model_type == 'job' and obj_id:
            get_object_or_404(JobNotification, id=obj_id).delete()
            messages.success(request, _('Job deleted.'))
        elif model_type == 'scheme' and obj_id:
            get_object_or_404(GovernmentScheme, id=obj_id).delete()
            messages.success(request, _('Scheme deleted.'))
        elif model_type == 'appointment' and obj_id:
            get_object_or_404(Appointment, id=obj_id).delete()
            messages.success(request, _('Appointment deleted.'))
        elif model_type == 'contact' and obj_id:
            get_object_or_404(Contact, id=obj_id).delete()
            messages.success(request, _('Contact deleted.'))
        elif model_type == 'form' and obj_id:
            get_object_or_404(DownloadForm, id=obj_id).delete()
            messages.success(request, _('Form deleted.'))
        elif model_type == 'servicecharge' and obj_id:
            get_object_or_404(ServiceCharge, id=obj_id).delete()
            messages.success(request, _('Service charge deleted.'))
        elif model_type == 'gallery' and obj_id:
            get_object_or_404(Gallery, id=obj_id).delete()
            messages.success(request, _('Gallery image deleted.'))

        cache.delete(DASHBOARD_CACHE_KEY)
        return redirect('superadmin_dashboard' if is_super else 'admin_dashboard')

    # Superadmin specific: edit user role
    if is_super and action == 'edit_user':
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('new_role')
        if user_id and new_role:
            user = get_object_or_404(User, id=user_id)
            user.role = new_role
            user.save()
            messages.success(request, _('User role updated.'))
        return redirect('superadmin_dashboard')

    return None  # no action handled

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

# =============================================================================
# AJAX ENDPOINT FOR DASHBOARD SECTIONS (Lazy Loading)
# =============================================================================

@login_required
@user_passes_test(is_admin)
def dashboard_section_data(request, section):
    """Return JSON data for a specific dashboard section."""
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
# PUBLIC VIEWS – with caching and pagination
# =============================================================================

@cache_page(60 * 5)  # 5 minutes
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

@cache_page(60 * 15)  # 15 minutes
def about(request):
    business = get_business()
    certifications = []
    if business and business.certifications:
        certifications = business.certifications.splitlines()

    context = {
        'business': business,
        'services': Service.objects.filter(active=True).only('name', 'icon'),
        'charges': ServiceCharge.objects.select_related('service').all().only('service__name', 'charge'),
        'certifications': certifications,
    }
    return render(request, 'aboutus.html', context)

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
            try:
                send_mail(
                    subject=f'New Contact Message from {contact.name}',
                    message=(
                        f'Name: {contact.name}\n'
                        f'Email: {contact.email}\n'
                        f'Phone: {contact.phone}\n'
                        f'Message:\n{contact.message}'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_EMAIL],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f"Failed to send contact email: {e}")
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
            form.save()
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

@cache_page(60 * 60)  # 1 hour
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

    # Compute rating statistics (for the entire queryset, not just the page)
    total_reviews = all_reviews.count()
    if total_reviews > 0:
        rating_avg = all_reviews.aggregate(avg=models.Avg('rating'))['avg']
        rating_counts = {}
        for i in range(1, 6):
            rating_counts[i] = all_reviews.filter(rating=i).count()
    else:
        rating_avg = 0
        rating_counts = {1:0, 2:0, 3:0, 4:0, 5:0}

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
# APPLICATION & DOCUMENT VIEWS (User) – with pagination
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
            application = form.save(commit=False)
            application.user = request.user
            application.service = service
            application.save()

            for i, doc_form in enumerate(formset.cleaned_data):
                if doc_form:
                    doc_name = required_docs[i].document_name if i < len(required_docs) else 'Other'
                    DocumentUpload.objects.create(
                        application=application,
                        document_name=doc_name,
                        file=doc_form['file'],
                        is_mandatory=True,
                    )
            messages.success(request, _('Your application has been submitted successfully.'))
            return redirect('my_applications')
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
    })

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

    return render(request, 'application_admin_detail.html', {
        'application': application,
        'documents': application.documents.all().only('id', 'document_name', 'file', 'is_mandatory', 'verified', 'uploaded_at'),
        'business': get_business(),
    })

# =============================================================================
# PDF SPLITTING VIEW
# =============================================================================

@login_required
@user_passes_test(is_admin)
def split_pdf(request, pk):
    document = get_object_or_404(DocumentUpload, pk=pk)
    app = document.application  # get the associated application

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

    # GET request
    return render(request, 'split_pdf.html', {
        'document': document,
        'app': app,
        'business': get_business(),
    })
