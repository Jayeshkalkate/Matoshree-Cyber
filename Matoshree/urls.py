"""
URL Configuration for Matoshree project.

The `urlpatterns` list routes URLs to views. For more information see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

urlpatterns = [
    # Django Admin – keep this if you use the built‑in admin
    path('admin/', admin.site.urls),

    # All application URLs (home, about, services, payment, etc.)
    # This includes everything defined in corematoshree/urls.py,
    # including:
    #   - Payment: /create-razorpay-order/, /payment/razorpay-webhook/, etc.
    #   - Public pages, dashboards, applications, etc.
    path('', include('corematoshree.urls')),

    # Language selection (i18n) – enables language switching via /i18n/setlang/
    path('i18n/', include('django.conf.urls.i18n')),
]

# Serve media and static files during development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Optional: Django Debug Toolbar (uncomment if installed)
    # import debug_toolbar
    # urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
    
