from django.shortcuts import render, redirect
from django.contrib import messages
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
)
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import CustomUserCreationForm, ProfileUpdateForm

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
    return render(request, 'register.html', {'form': form})

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
    return render(request, 'profile.html', {'form': form})

# Role check functions
def is_admin(user):
    return user.is_authenticated and user.role in ['admin', 'superadmin']

def is_superadmin(user):
    return user.is_authenticated and user.role == 'superadmin'

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Render the admin dashboard HTML (or pass dynamic data)
    return render(request, 'admindashboard.html', {'business': business()})

@login_required
@user_passes_test(is_superadmin)
def superadmin_dashboard(request):
    return render(request, 'superadmindashboard.html', {'business': business()})

def business():
    return BusinessInfo.objects.first()


# ==========================
# Home
# ==========================
def home(request):
    context = {
        "business": business(),
        "services": Service.objects.filter(active=True)[:8],
        "announcements": Announcement.objects.all()[:5],
        "reviews": Review.objects.filter(approved=True)[:6],
        "gallery": Gallery.objects.all()[:8],
    }
    return render(request, "homepage.html", context)


# ==========================
# About
# ==========================
def about(request):
    return render(
        request,
        "aboutus.html",
        {"business": business()},
    )


# ==========================
# Services
# ==========================
def services(request):
    context = {
        "business": business(),
        "services": Service.objects.filter(active=True),
    }
    return render(request, "services.html", context)


# ==========================
# Gallery
# ==========================
def gallery(request):
    images = Gallery.objects.all().order_by('-id')
    paginator = Paginator(images, 12)
    page = request.GET.get("page")
    try:
        images_page = paginator.page(page)
    except PageNotAnInteger:
        images_page = paginator.page(1)
    except EmptyPage:
        images_page = paginator.page(paginator.num_pages)

    context = {
        "business": business(),
        "images": images_page,
    }
    return render(request, "gallery.html", context)


# ==========================
# Contact
# ==========================
def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            contact_instance = form.save()

            # Send email notification (optional)
            try:
                send_mail(
                    subject=f"New Contact Message from {contact_instance.name}",
                    message=f"Name: {contact_instance.name}\n"
                            f"Email: {contact_instance.email}\n"
                            f"Phone: {contact_instance.phone}\n"
                            f"Message:\n{contact_instance.message}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_EMAIL],  # set in settings
                    fail_silently=True,
                )
            except Exception:
                # Log error if needed; we ignore to not break user experience
                pass

            messages.success(request, "Your message has been sent successfully.")
            return redirect("contact")
        # else: fall through to render with bound form and errors
    else:
        form = ContactForm()

    context = {
        "business": business(),
        "form": form,
    }
    return render(request, "contactus.html", context)


# ==========================
# Appointment
# ==========================
def appointment(request):
    if request.method == "POST":
        form = AppointmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Appointment booked successfully.")
            return redirect("appointment")
        else:
            messages.error(request, "Please correct the errors below.")
            # fall through to render with bound form and errors
    else:
        form = AppointmentForm()

    context = {
        "business": business(),
        "form": form,
        "services": Service.objects.filter(active=True),
    }
    return render(request, "appointment.html", context)


# ==========================
# FAQ
# ==========================
def faq(request):
    context = {
        "business": business(),
        "faqs": FAQ.objects.all(),
    }
    return render(request, "faq.html", context)


# ==========================
# Required Documents
# ==========================
def documents(request):
    services = Service.objects.filter(active=True).prefetch_related("requireddocument_set")
    paginator = Paginator(services, 10)  # show 10 services per page
    page = request.GET.get("page")
    try:
        services_page = paginator.page(page)
    except PageNotAnInteger:
        services_page = paginator.page(1)
    except EmptyPage:
        services_page = paginator.page(paginator.num_pages)

    context = {
        "business": business(),
        "services": services_page,
    }
    return render(request, "required_document.html", context)


# ==========================
# Download Forms
# ==========================
def downloads(request):
    context = {
        "business": business(),
        "forms": DownloadForm.objects.all(),
    }
    return render(request, "download_forms.html", context)


# ==========================
# Service Charges
# ==========================
def charges(request):
    context = {
        "business": business(),
        "charges": ServiceCharge.objects.select_related("service"),
    }
    return render(request, "service_charges.html", context)


# ==========================
# Customer Reviews
# ==========================
def reviews(request):
    all_reviews = Review.objects.filter(approved=True)
    paginator = Paginator(all_reviews, 10)  # show 10 reviews per page
    page = request.GET.get("page")
    try:
        reviews_page = paginator.page(page)
    except PageNotAnInteger:
        reviews_page = paginator.page(1)
    except EmptyPage:
        reviews_page = paginator.page(paginator.num_pages)

    context = {
        "business": business(),
        "reviews": reviews_page,
        "form": ReviewForm(),
    }
    return render(request, "customer_reviews.html", context)


# ==========================
# Submit Review
# ==========================
def submit_review(request):
    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.approved = False
            review.save()
            messages.success(
                request,
                "Thank you! Your review will appear after admin approval."
            )
        else:
            messages.error(
                request,
                "Please correct the errors in the review form."
            )
    return redirect("reviews")


# ==========================
# Announcements
# ==========================
def announcements(request):
    announcements_list = Announcement.objects.all()
    paginator = Paginator(announcements_list, 10)  # show 10 announcements per page
    page = request.GET.get("page")
    try:
        announcements_page = paginator.page(page)
    except PageNotAnInteger:
        announcements_page = paginator.page(1)
    except EmptyPage:
        announcements_page = paginator.page(paginator.num_pages)

    context = {
        "business": business(),
        "announcements": announcements_page,
    }
    return render(request, "announcements.html", context)


# ==========================
# Government Schemes
# ==========================
def government_schemes(request):
    schemes_list = GovernmentScheme.objects.all()
    paginator = Paginator(schemes_list, 10)  # show 10 schemes per page
    page = request.GET.get("page")
    try:
        schemes_page = paginator.page(page)
    except PageNotAnInteger:
        schemes_page = paginator.page(1)
    except EmptyPage:
        schemes_page = paginator.page(paginator.num_pages)

    context = {
        "business": business(),
        "schemes": schemes_page,
    }
    return render(request, "government_schemes.html", context)


# ==========================
# Jobs
# ==========================
def jobs(request):
    jobs_list = JobNotification.objects.order_by("last_date")
    paginator = Paginator(jobs_list, 10)  # show 10 jobs per page
    page = request.GET.get("page")
    try:
        jobs_page = paginator.page(page)
    except PageNotAnInteger:
        jobs_page = paginator.page(1)
    except EmptyPage:
        jobs_page = paginator.page(paginator.num_pages)

    context = {
        "business": business(),
        "jobs": jobs_page,
    }
    return render(request, "jobs.html", context)

