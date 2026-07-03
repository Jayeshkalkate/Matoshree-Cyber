# =============================================================================
# IMPORTS
# =============================================================================
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.mail import send_mail
from django.conf import settings

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
    return render(request, 'admindashboard.html', {'business': get_business()})


@login_required
@user_passes_test(is_superadmin)
def superadmin_dashboard(request):
    return render(request, 'superadmindashboard.html', {'business': get_business()})


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
    
