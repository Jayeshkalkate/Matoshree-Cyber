"""
URL Configuration for the core application.
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

# app_name = 'core'  # Commented out to avoid breaking existing templates

urlpatterns = [
    # =============================================
    # Public Pages
    # =============================================
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    path('gallery/', views.gallery, name='gallery'),
    path('contact/', views.contact, name='contact'),
    path('appointment/', views.appointment, name='appointment'),
    path('faq/', views.faq, name='faq'),
    path('documents/', views.documents, name='documents'),
    path('downloads/', views.downloads, name='downloads'),
    path('charges/', views.charges, name='charges'),
    path('reviews/', views.reviews, name='reviews'),
    path('announcements/', views.announcements, name='announcements'),
    path('government-schemes/', views.government_schemes, name='government_schemes'),
    path('jobs/', views.jobs, name='jobs'),
    path('team/', views.team, name='team'),
    
    # Review submission (POST only)
    path('submit-review/', views.submit_review, name='submit_review'),

    # =============================================
    # User Authentication & Profile
    # =============================================
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='password_change.html'), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_change_done.html'), name='password_change_done'),

    # =============================================
    # User Applications & Document Management
    # =============================================
    path('apply/<int:service_id>/', views.apply_service, name='apply_service'),
    path('my-applications/', views.my_applications, name='my_applications'),
    path('application/<int:app_id>/', views.application_detail, name='application_detail'),

    # =============================================
    # Admin Dashboard & Management
    # =============================================
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('superadmin-dashboard/', views.superadmin_dashboard, name='superadmin_dashboard'),

    # Admin only: application details (via AJAX and full view)
    path('application-detail/<int:app_id>/', views.application_detail_ajax, name='application_detail_ajax'),
    
    # Admin full view for application details (with document management)
    path('admin-app/<int:app_id>/', views.application_admin_detail, name='application_admin_detail'),

    # PDF splitting (admin only)
    path('pdf/<int:pk>/split/', views.split_pdf, name='split_pdf'),
]