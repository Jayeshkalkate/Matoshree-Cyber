# corematoshree/utils.py
import logging
from datetime import datetime
from django.core.cache import cache
from django.conf import settings
from .models import BusinessInfo, PaymentSettings

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Business & Payment helpers (no changes needed, but kept robust)
# -------------------------------------------------------------------

def get_business():
    cache_key = 'business_info'
    business = cache.get(cache_key)
    if business is None:
        try:
            business = BusinessInfo.objects.first()
        except Exception as e:
            logger.error(f"Failed to fetch BusinessInfo: {e}")
            business = None
        cache.set(cache_key, business, 60 * 60)
    return business


def get_payment_settings():
    cache_key = 'payment_settings'
    settings_obj = cache.get(cache_key)
    if settings_obj is None:
        try:
            settings_obj = PaymentSettings.objects.filter(is_active=True).first()
            if not settings_obj:
                settings_obj = PaymentSettings.objects.create(is_active=False)
        except Exception as e:
            logger.error(f"Failed to fetch PaymentSettings: {e}")
            settings_obj = None
        cache.set(cache_key, settings_obj, 60 * 60)
    return settings_obj


def is_admin(user):
    return user.is_authenticated and user.role in ('admin', 'superadmin')


def is_superadmin(user):
    return user.is_authenticated and user.role == 'superadmin'


# -------------------------------------------------------------------
# External jobs feed – completely safe with fallbacks
# -------------------------------------------------------------------

def fetch_external_jobs():
    """
    Fetch job listings from the RSS feed of majhinaukri.in.
    Returns a list of dicts with keys: title, organization, description,
    apply_link, last_date.
    If any error occurs (missing packages, network failure, parse errors),
    returns an empty list and logs the issue.
    """
    # Try to import feedparser and dateutil only when needed
    try:
        import feedparser
    except ImportError:
        logger.error("feedparser is not installed. External jobs feed disabled.")
        return []

    try:
        from dateutil import parser as date_parser
    except ImportError:
        logger.warning("python-dateutil not installed. Date parsing will be limited.")
        date_parser = None

    feed_url = getattr(
        settings,
        'EXTERNAL_JOBS_RSS_URL',
        'https://majhinaukri.in/feed/'
    )

    cache_key = 'external_jobs_feed'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        feed = feedparser.parse(feed_url)
        # Check for feed parsing errors
        if feed.get('bozo', False):
            logger.warning(f"Feed parsing error: {feed.get('bozo_exception', 'Unknown')}")

        jobs = []
        for entry in feed.entries:
            title = entry.get('title', '').strip()
            link = entry.get('link', '#')
            description = entry.get('description', '') or entry.get('summary', '')
            pub_date = entry.get('published', entry.get('pubDate', ''))

            # Extract organization from title
            org = 'Various'
            if ':' in title:
                org, title = title.split(':', 1)
                org = org.strip()
                title = title.strip()
            elif ' - ' in title:
                parts = title.split(' - ', 1)
                org = parts[0].strip()
                title = parts[1].strip() if len(parts) > 1 else title

            # Parse date – try dateutil first, fallback to strptime
            last_date = None
            if pub_date and date_parser:
                try:
                    last_date = date_parser.parse(pub_date)
                except Exception as e:
                    logger.debug(f"Dateutil parsing failed for '{pub_date}': {e}")
                    # fall through to next method
            if pub_date and last_date is None:
                # Try common RSS date formats
                for fmt in ('%a, %d %b %Y %H:%M:%S %z',
                            '%a, %d %b %Y %H:%M:%S %Z',
                            '%Y-%m-%dT%H:%M:%S%z',
                            '%Y-%m-%d %H:%M:%S'):
                    try:
                        last_date = datetime.strptime(pub_date, fmt)
                        break
                    except ValueError:
                        continue

            jobs.append({
                'title': title,
                'organization': org,
                'description': description,
                'apply_link': link,
                'last_date': last_date,
                'source': 'external'
            })

        # Cache for 1 hour (only if we have entries, otherwise cache empty list too)
        cache.set(cache_key, jobs, 60 * 60)
        return jobs

    except Exception as e:
        logger.error(f"Failed to fetch or parse external jobs: {e}", exc_info=True)
        # Cache empty list to avoid hammering the feed on every request
        cache.set(cache_key, [], 60 * 5)   # shorter cache for errors
        return []
