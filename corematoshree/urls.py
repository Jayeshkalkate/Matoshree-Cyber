from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from corematoshree import views

urlpatterns = [
     
    # ==========================
    # AUTHENTICATION
    # ==========================
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('profile/', views.profile, name='profile'),

    # Password Reset (custom views)
    path('password-reset/',
         views.CustomPasswordResetView.as_view(),
         name='password_reset'),
    path('password-reset/done/',
         views.CustomPasswordResetDoneView.as_view(),
         name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/',
         views.CustomPasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('password-reset/complete/',
         views.CustomPasswordResetCompleteView.as_view(),
         name='password_reset_complete'),

    # ==========================
    # DASHBOARDS & REPORTS
    # ==========================
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('superadmin-dashboard/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('dashboard-section/<str:section>/', views.dashboard_section_data, name='dashboard_section_data'),
    path('reports/', views.reports_dashboard, name='reports_dashboard'),

    # ==========================
    # PUBLIC PAGES
    # ==========================
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('team/', views.team, name='team'),
    path('services/', views.services, name='services'),
    path('gallery/', views.gallery, name='gallery'),
    path('contact/', views.contact, name='contact'),
    path('appointment/', views.appointment, name='appointment'),
    path('faq/', views.faq, name='faq'),
    path('documents/', views.documents, name='documents'),
    path('downloads/', views.downloads, name='downloads'),
    path('charges/', views.charges, name='charges'),
    path('reviews/', views.reviews, name='reviews'),
    path('submit-review/', views.submit_review, name='submit_review'),
    path('announcements/', views.announcements, name='announcements'),
    path('schemes/', views.government_schemes, name='government_schemes'),
    path('jobs/', views.jobs, name='jobs'),

    # ==========================
    # APPLICATIONS (User)
    # ==========================
    path('apply/<int:service_id>/', views.apply_service, name='apply_service'),
    path('my-applications/', views.my_applications, name='my_applications'),
    path('application/<int:app_id>/', views.application_detail, name='application_detail'),

    # ==========================
    # PAYMENT CHECKOUT (pending application)
    # ==========================
    path('payment-checkout/<int:service_id>/', views.payment_checkout, name='payment_checkout'),
    path('create-application-from-session/', views.create_application_from_session, name='create_application_from_session'),
    path('create-razorpay-order-pending/<int:service_id>/', views.create_razorpay_order_pending, name='create_razorpay_order_pending'),
    
    # ==========================
    # APPLICATIONS (Admin)
    # ==========================
    path('application-admin/<int:app_id>/', views.application_admin_detail, name='application_admin_detail'),
    path('application-ajax/<int:app_id>/', views.application_detail_ajax, name='application_detail_ajax'),

    # ==========================
    # PDF SPLIT
    # ==========================
    path('split-pdf/<int:pk>/', views.split_pdf, name='split_pdf'),

    # ==========================
    # PAYMENT GATEWAY
    # ==========================
    
    # ---- Webhook (public, no login) ----
    path('payment/razorpay-webhook/', views.razorpay_webhook, name='razorpay_webhook'),

    # ---- Razorpay order creation (login required) ----
    # For existing applications (app_id > 0)
    path('payment/create-order/<int:app_id>/', views.create_payment, name='create_payment'),
    path('create-razorpay-order/<int:app_id>/', views.create_razorpay_order, name='create_razorpay_order'),

    # ---- Razorpay verification (login required) ----
    path('payment/verify-payment/', views.verify_razorpay_payment, name='verify_payment'),
    path('verify-razorpay-payment/', views.verify_razorpay_payment, name='verify_razorpay_payment'),

    # ---- Manual UPI confirmation (login required) ----
    # For pending (app_id=0) or existing (app_id>0)
    path('mark-payment-done/<int:app_id>/', views.mark_payment_done, name='mark_payment_done'),

    # ---- Receipt download (login required) ----
    path('download-receipt/<int:app_id>/', views.download_receipt, name='download_receipt'),
]

# ==========================
# SERVE MEDIA & STATIC FILES (development only)
# ==========================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
