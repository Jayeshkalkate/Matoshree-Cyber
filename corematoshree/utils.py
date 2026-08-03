# corematoshree/utils.py
from django.core.cache import cache
from .models import BusinessInfo, PaymentSettings
import feedparser
from datetime import datetime
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def get_business():
    cache_key = 'business_info'
    business = cache.get(cache_key)
    if business is None:
        try:
            business = BusinessInfo.objects.first()
        except Exception:
            business = None
        cache.set(cache_key, business, 60 * 60)
    return business

def get_payment_settings():
    cache_key = 'payment_settings'
    settings_obj = cache.get(cache_key)
    if settings_obj is None:
        settings_obj = PaymentSettings.objects.filter(is_active=True).first()
        if not settings_obj:
            settings_obj = PaymentSettings.objects.create(is_active=False)
        cache.set(cache_key, settings_obj, 60 * 60)
    return settings_obj

def is_admin(user):
    return user.is_authenticated and user.role in ('admin', 'superadmin')

def is_superadmin(user):
    return user.is_authenticated and user.role == 'superadmin'

def fetch_external_jobs():
    """
    Fetch job listings from the RSS feed of majhinaukri.in.
    Returns a list of dicts with keys: title, organization, description,
    apply_link, last_date.
    """
    feed_url = getattr(settings, 'EXTERNAL_JOBS_RSS_URL', 
                       'https://majhinaukri.in/feed/')

    cache_key = 'external_jobs_feed'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        feed = feedparser.parse(feed_url)
        jobs = []
        for entry in feed.entries:
            title = entry.get('title', '')
            link = entry.get('link', '#')
            description = entry.get('description', '') or entry.get('summary', '')
            pub_date = entry.get('published', entry.get('pubDate', ''))

            # Try to extract organization
            org = 'Various'
            if ':' in title:
                org, title = title.split(':', 1)
                org = org.strip()
                title = title.strip()
            elif ' - ' in title:
                parts = title.split(' - ', 1)
                org = parts[0].strip()
                title = parts[1].strip() if len(parts) > 1 else title

            # Parse date (if available)
            last_date = None
            if pub_date:
                try:
                    # Common RSS date formats
                    from dateutil import parser
                    last_date = parser.parse(pub_date)
                except:
                    try:
                        # fallback to simple parsing
                        last_date = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %z')
                    except:
                        pass

            jobs.append({
                'title': title,
                'organization': org,
                'description': description,
                'apply_link': link,
                'last_date': last_date,
                'source': 'external'   # mark source
            })

        # Cache for 1 hour
        cache.set(cache_key, jobs, 60 * 60)
        return jobs

    except Exception as e:
        logger.error(f"Failed to fetch external jobs: {e}")
        return []