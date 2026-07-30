from django.contrib.sitemaps import Sitemap
from .models import Service, Announcement

class ServiceSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Service.objects.filter(active=True)

    # Comment out lastmod until you add updated_at to Service model
    # def lastmod(self, obj):
    #     return obj.updated_at

class AnnouncementSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Announcement.objects.all()

    # def lastmod(self, obj):
    #     return obj.updated_at