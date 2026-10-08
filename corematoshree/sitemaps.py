from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils.text import slugify
from .models import Service


class ServiceSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Service.objects.filter(active=True)

    def location(self, obj):
        return reverse('service_detail', kwargs={'slug': slugify(obj.name)})

    def lastmod(self, obj):
        return obj.updated_at


class StaticPublicSitemap(Sitemap):
    priority = 0.5
    changefreq = 'weekly'
    pages = (
        'home', 'about', 'team', 'services', 'gallery', 'contact', 'appointment',
        'faq', 'documents', 'downloads', 'charges', 'reviews', 'announcements',
        'government_schemes', 'jobs', 'terms', 'privacy', 'track_application',
    )

    def items(self):
        return self.pages

    def location(self, item):
        return reverse(item)
