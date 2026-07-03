# =============================================================================
# IMPORTS
# =============================================================================

from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from .forms import ServiceForm, AnnouncementForm

from .models import (
    Review,
    Announcement,
    Gallery,
    Service,
    ServiceCharge,
    DownloadForm,
    GovernmentScheme,
    JobNotification,
    FAQ,
    BusinessInfo,
)
from .forms import (
    ContactForm,
    AppointmentForm,
    ReviewForm,
    CustomUserCreationForm,
    ProfileUpdateForm,
)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test

# Import all dashboard forms
from .forms import (
    ServiceForm, AnnouncementForm, JobNotificationForm,
    GovernmentSchemeForm, AppointmentForm, ContactFormDashboard,
    DownloadFormForm
)

# Import all models (already imported, but ensure all are imported)
from .models import (
    Service, Announcement, JobNotification, GovernmentScheme,
    Appointment, Contact, DownloadForm, Review, Gallery,
    ServiceCharge, RequiredDocument, FAQ, BusinessInfo
)

# =============================================================================
# HELPERS / CONTEXT
# =============================================================================
def get_business():
    """Return the first (and only) BusinessInfo instance."""
    return BusinessInfo.objects.first()


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

    # Initialize empty forms for each model (for adding)
    service_form = ServiceForm()
    announcement_form = AnnouncementForm()
    job_form = JobNotificationForm()
    scheme_form = GovernmentSchemeForm()
    appointment_form = AppointmentForm()
    contact_form = ContactFormDashboard()
    download_form = DownloadFormForm()

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
                form = GovernmentSchemeForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Scheme added.')
                else:
                    messages.error(request, 'Error adding scheme.')
            elif model_type == 'appointment':
                form = AppointmentForm(request.POST)
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
            return redirect('admin_dashboard')

        elif action == 'edit':
            # Get the instance and update
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
            # Add similar for other models...
            return redirect('admin_dashboard')

        elif action == 'delete':
            if model_type == 'service' and obj_id:
                get_object_or_404(Service, id=obj_id).delete()
                messages.success(request, 'Service deleted.')
            elif model_type == 'announcement' and obj_id:
                get_object_or_404(Announcement, id=obj_id).delete()
                messages.success(request, 'Announcement deleted.')
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
            return redirect('admin_dashboard')

    context = {
        'services': services,
        'appointments': appointments,
        'contacts': contacts,
        'announcements': announcements,
        'jobs': jobs,
        'schemes': schemes,
        'forms_list': forms_list,
        'service_form': service_form,
        'announcement_form': announcement_form,
        'job_form': job_form,
        'scheme_form': scheme_form,
        'appointment_form': appointment_form,
        'contact_form': contact_form,
        'download_form': download_form,
        'business': get_business(),
    }
    return render(request, 'admindashboard.html', context)

@login_required
@user_passes_test(is_superadmin)
def superadmin_dashboard(request):
    # Reuse all data from admin_dashboard
    services = Service.objects.all().order_by('name')
    appointments = Appointment.objects.all().order_by('-appointment_date')
    contacts = Contact.objects.all().order_by('-created_at')
    announcements = Announcement.objects.all().order_by('-created_at')
    jobs = JobNotification.objects.all().order_by('-last_date')
    schemes = GovernmentScheme.objects.all().order_by('-last_date')
    forms_list = DownloadForm.objects.all().order_by('-uploaded_at')
    users = User.objects.all().order_by('username')

    # Forms (same as admin)
    service_form = ServiceForm()
    announcement_form = AnnouncementForm()
    job_form = JobNotificationForm()
    scheme_form = GovernmentSchemeForm()
    appointment_form = AppointmentForm()
    contact_form = ContactFormDashboard()
    download_form = DownloadFormForm()

    # Handle POST
    if request.method == 'POST':
        action = request.POST.get('action')
        model_type = request.POST.get('model_type')
        obj_id = request.POST.get('id')

        # ---- Same add/edit/delete logic as admin_dashboard ----
        # (copy the entire if/elif block from admin_dashboard)
        # Add this extra block for user role update:
        if action == 'edit_user':
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('new_role')
            if user_id and new_role:
                user = get_object_or_404(User, id=user_id)
                user.role = new_role
                user.save()
                messages.success(request, f"User {user.username} role updated to {new_role}.")
            return redirect('superadmin_dashboard')

        # ... (add the rest of the logic from admin_dashboard)

    context = {
        'services': services,
        'appointments': appointments,
        'contacts': contacts,
        'announcements': announcements,
        'jobs': jobs,
        'schemes': schemes,
        'forms_list': forms_list,
        'users': users,
        'service_form': service_form,
        'announcement_form': announcement_form,
        'job_form': job_form,
        'scheme_form': scheme_form,
        'appointment_form': appointment_form,
        'contact_form': contact_form,
        'download_form': download_form,
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
    }
    return render(request, 'homepage.html', context)


def about(request):
    return render(request, 'aboutus.html', {'business': get_business()})


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

            # Send email notification (fail silently)
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
                # Log the error if needed; we ignore to avoid breaking UX
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
    services_qs = Service.objects.filter(active=True).prefetch_related('requireddocument_set')
    paginator = Paginator(services_qs, 10)
    page = request.GET.get('page')

    try:
        services_page = paginator.page(page)
    except PageNotAnInteger:
        services_page = paginator.page(1)
    except EmptyPage:
        services_page = paginator.page(paginator.num_pages)

    return render(request, 'required_document.html', {
        'business': get_business(),
        'services': services_page,
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
    all_reviews = Review.objects.filter(approved=True)
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
            review.approved = False  # requires admin approval
            review.save()
            messages.success(
                request,
                'Thank you! Your review will appear after admin approval.'
            )
        else:
            messages.error(request, 'Please correct the errors in the review form.')
    return redirect('reviews')


def announcements(request):
    announcements_qs = Announcement.objects.all()
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
    schemes_qs = GovernmentScheme.objects.all()
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
@user_passes_test(is_admin)   # or is_superadmin
def dashboard_services(request):
    services = Service.objects.all().order_by('name')
    form = ServiceForm()
    if request.method == 'POST':
        if 'add' in request.POST:
            form = ServiceForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Service added.')
                return redirect('dashboard_services')
        elif 'delete' in request.POST:
            service_id = request.POST.get('service_id')
            service = get_object_or_404(Service, id=service_id)
            service.delete()
            messages.success(request, 'Service deleted.')
            return redirect('dashboard_services')
        elif 'edit' in request.POST:
            service_id = request.POST.get('service_id')
            service = get_object_or_404(Service, id=service_id)
            form = ServiceForm(request.POST, instance=service)
            if form.is_valid():
                form.save()
                messages.success(request, 'Service updated.')
                return redirect('dashboard_services')
    context = {
        'services': services,
        'form': form,
    }
    return render(request, 'dashboard_services.html', context)