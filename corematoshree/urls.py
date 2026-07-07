from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [

    # Home
    path('', views.home, name='home'),

    # About
    path('about/', views.about, name='about'),

    # Services
    path('services/', views.services, name='services'),

    # Gallery
    path('gallery/', views.gallery, name='gallery'),

    # Contact
    path('contact/', views.contact, name='contact'),

    # Appointment
    path('appointment/', views.appointment, name='appointment'),

    # FAQ
    path('faq/', views.faq, name='faq'),

    # Required Documents
    path('documents/', views.documents, name='documents'),

    # Download Forms
    path('downloads/', views.downloads, name='downloads'),

    # Service Charges
    path('charges/', views.charges, name='charges'),

    # Customer Reviews
    path('reviews/', views.reviews, name='reviews'),

    # Announcements
    path('announcements/', views.announcements, name='announcements'),

    # Government Schemes
    path('government-schemes/', views.government_schemes, name='government_schemes'),

    # Job Notifications
    path('jobs/', views.jobs, name='jobs'),
    
    path('submit-review/', views.submit_review, name='submit_review'),
    
    # Profile & Auth
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('superadmin-dashboard/', views.superadmin_dashboard, name='superadmin_dashboard'),

    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='password_change.html'), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_change_done.html'), name='password_change_done'),

]