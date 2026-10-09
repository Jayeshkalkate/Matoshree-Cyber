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
from corematoshree.security import rate_limit

# Django admin has a separate login endpoint; throttle password POST attempts too.
if not getattr(admin.site, "_matoshree_login_rate_limited", False):
    admin.site.login = rate_limit(
        "django-admin-login", limit=10, window_seconds=900,
        identity_fields=("username",), methods=("POST",),
    )(admin.site.login)
    admin.site._matoshree_login_rate_limited = True

urlpatterns = [
    # Django Admin – keep this if you use the built‑in admin
    path('admin/', admin.site.urls),

    # All application URLs (home, about, services, payment, etc.)
    path('', include('corematoshree.urls')),

    # Language selection (i18n) – enables language switching via /i18n/setlang/
    path('i18n/', include('django.conf.urls.i18n')),
]

# Serve media and static files during development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Optional: custom error pages
# handler404 = 'your_app.views.custom_404'
# handler500 = 'your_app.views.custom_500'
