from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from corematoshree import views
from django.contrib.sitemaps.views import sitemap
from .sitemaps import ServiceSitemap, StaticPublicSitemap
from django.views.generic import TemplateView 
from .views import robots_txt
from .authentication import AuditedLoginView, AuditedLogoutView, google_oauth_start, google_oauth_callback
from .security import rate_limit

sitemaps = {
    'services': ServiceSitemap,
    'static': StaticPublicSitemap,
}

handler403 = views.custom_403
handler404 = views.custom_404
handler500 = views.custom_500

urlpatterns = [
    # ==========================
    # AUTHENTICATION
    # ==========================
    path('register/', rate_limit('register', limit=8, window_seconds=3600, identity_fields=('username', 'email'), methods=('POST',))(views.register), name='register'),
    path('login/', rate_limit('login', limit=10, window_seconds=900, identity_fields=('username',), methods=('POST',))(AuditedLoginView.as_view()), name='login'),
    path('logout/', AuditedLogoutView.as_view(next_page='home'), name='logout'),
    path('auth/google/', google_oauth_start, name='google_oauth_start'),
    path('auth/google/callback/', google_oauth_callback, name='google_oauth_callback'),
    path('profile/', views.profile, name='profile'),

    # Password Reset (custom views)
    path('password-reset/', rate_limit('password-reset', limit=5, window_seconds=900, identity_fields=('email',), methods=('POST',))(views.CustomPasswordResetView.as_view()), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # Password Change
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change/done/', views.CustomPasswordChangeDoneView.as_view(), name='password_change_done'),

    # ==========================
    # DASHBOARDS & REPORTS
    # ==========================
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('superadmin-dashboard/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('dashboard-section/<str:section>/', views.dashboard_section_data, name='dashboard_section_data'),
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('reports/applications.csv', views.export_applications_csv, name='export_applications_csv'),

    # ==========================
    # PUBLIC PAGES
    # ==========================
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('team/', views.team, name='team'),
    path('services/', views.services, name='services'),
    path('services/<slug:slug>/', views.service_detail, name='service_detail'),
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
    path('track-application/', rate_limit('track-application', limit=15, window_seconds=300, identity_fields=('application_number',))(views.track_application), name='track_application'),
    path('notifications/', views.notifications, name='notifications'),
    path('document/<int:doc_id>/download/', views.document_download, name='document_download'),
    path('application/<int:app_id>/', views.application_detail, name='application_detail'),

    # ==========================
    # PAYMENT CHECKOUT (using app_id)
    # ==========================
    path('payment-checkout/<int:app_id>/', views.payment_checkout, name='payment_checkout'),

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
    # PAYMENT GATEWAY – Razorpay
    # ==========================
    path('create-razorpay-order/', rate_limit('razorpay-order', limit=6, window_seconds=300, identity_fields=('app_id',), methods=('POST',))(views.create_razorpay_order), name='create_razorpay_order'),
    path('payment-success/', rate_limit('payment-success', limit=10, window_seconds=300, identity_fields=('razorpay_order_id',), methods=('POST',))(views.payment_success), name='payment_success'),
    path('payment-failure/', views.payment_failure, name='payment_failure'),
    # Verified Razorpay webhook (configure its secret before enabling at the provider)
    path('razorpay-webhook/', views.razorpay_webhook, name='razorpay_webhook'),

    # ---- Manual UPI/Cash confirmation (admin override) ----
    path('mark-payment-done/<int:app_id>/', views.mark_payment_done, name='mark_payment_done'),

    # ---- Receipt download (login required) ----
    path('download-receipt/<int:app_id>/', views.download_receipt, name='download_receipt'),

    # ==========================
    # STATIC PAGES & SEO
    # ==========================
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('googleb2111897b41dceb9.html', TemplateView.as_view(template_name='googleb2111897b41dceb9.html'), name='google_verify'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt, name='robots'),
    path('healthz/', views.healthz, name='healthz'),
]

# Serve media & static in development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
