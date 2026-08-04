import logging
import re
from datetime import datetime
from django.core.cache import cache
from django.conf import settings
from .models import BusinessInfo, PaymentSettings
import time

logger = logging.getLogger(__name__)

# ─── Use cloudscraper if available, else fallback to requests ───
try:
    import cloudscraper
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True,
            'mobile': False
        }
    )
    logger.info("✅ cloudscraper loaded in utils – will bypass 403/Cloudflare")
except ImportError:
    import requests
    scraper = requests
    logger.warning("⚠️ cloudscraper not installed in utils – using requests (may get 403)")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def fetch_with_retry(url, timeout=25, retries=3):
    """Fetch URL with retries using the selected scraper."""
    for attempt in range(retries):
        try:
            response = scraper.get(url, timeout=timeout, headers=HEADERS)
            response.raise_for_status()
            return response
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"Attempt {attempt+1}/{retries} for {url} failed: {e}. Retrying in {wait}s...")
            if attempt == retries - 1:
                raise
            time.sleep(wait)
    return None

# -------------------------------------------------------------------
# Business & Payment helpers (unchanged)
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

def compute_payment_breakdown(service_amount, gst_rate=0.18, fee_percent=2.0, fee_fixed=0.0):
    """
    Returns dict with breakdown:
    {
        'service_amount': Decimal,
        'fee': Decimal,
        'gst_on_fee': Decimal,
        'total': Decimal
    }
    """
    from decimal import Decimal, ROUND_HALF_UP
    service_amount = Decimal(str(service_amount))
    fee = (service_amount * Decimal(str(fee_percent)) / 100) + Decimal(str(fee_fixed))
    fee = fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    gst_on_fee = fee * Decimal(str(gst_rate))
    gst_on_fee = gst_on_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = service_amount + fee + gst_on_fee
    total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        'service_amount': service_amount,
        'fee': fee,
        'gst_on_fee': gst_on_fee,
        'total': total,
    }

# -------------------------------------------------------------------
# External jobs feed – now using cloudscraper + retry
# -------------------------------------------------------------------

def fetch_external_jobs():
    """
    Fetch job listings from the Jobful API (freejobalert.com).
    If the API fails, fallback to RSS feed.
    Returns a list of dicts with keys: title, organization, description,
    apply_link, last_date, source.
    """
    cache_key = 'external_jobs_feed'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    api_url = getattr(settings, 'EXTERNAL_JOBS_API_URL', 
                      'http://localhost:3000/freejobalert/gov/other-all-india-exam')
    timeout = getattr(settings, 'EXTERNAL_JOBS_TIMEOUT', 25)
    limit = getattr(settings, 'EXTERNAL_JOBS_LIMIT', 50)

    # ---- 1. Try Jobful API with retry ----
    jobs = []
    try:
        response = fetch_with_retry(api_url, timeout=timeout)
        if response:
            data = response.json()
            if isinstance(data, list):
                for item in data[:limit]:
                    title = item.get('postName', '').strip()
                    organization = item.get('postBoard', 'Various').strip()
                    link = item.get('link', '#')
                    last_date_str = item.get('lastDate', '').strip()
                    qualification = item.get('qualification', '').strip()
                    advt_no = item.get('advtNo', '').strip()
                    post_date = item.get('postDate', '').strip()

                    # Build description
                    desc_parts = []
                    if qualification:
                        desc_parts.append(f"Qualification: {qualification}")
                    if advt_no:
                        desc_parts.append(f"Advt No: {advt_no}")
                    if post_date:
                        desc_parts.append(f"Posted: {post_date}")
                    description = " | ".join(desc_parts) if desc_parts else title

                    # Parse last_date
                    last_date = None
                    if last_date_str:
                        match = re.search(r'(\d{2}-\d{2}-\d{4})', last_date_str)
                        if match:
                            try:
                                last_date = datetime.strptime(match.group(1), '%d-%m-%Y').date()
                            except ValueError:
                                pass

                    jobs.append({
                        'title': title,
                        'organization': organization,
                        'description': description,
                        'apply_link': link,
                        'last_date': last_date,
                        'source': 'external'
                    })

                cache.set(cache_key, jobs, 60 * 60)
                return jobs
            else:
                logger.warning("Jobful API returned non-list data, falling back to RSS.")
        else:
            logger.warning("Jobful API request failed, falling back to RSS.")
    except Exception as e:
        logger.warning(f"Jobful API failed: {e}, falling back to RSS.")

    # ---- 2. Fallback: RSS feed (majhinaukri.in) ----
    try:
        import feedparser
        from dateutil import parser as date_parser

        feed_url = getattr(settings, 'EXTERNAL_JOBS_RSS_URL', 'https://majhinaukri.in/feed/')
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            title = entry.get('title', '').strip()
            link = entry.get('link', '#')
            description = entry.get('description', '') or entry.get('summary', '')
            pub_date = entry.get('published', entry.get('pubDate', ''))

            # Extract organization
            org = 'Various'
            if ':' in title:
                org, title = title.split(':', 1)
                org = org.strip()
                title = title.strip()
            elif ' - ' in title:
                parts = title.split(' - ', 1)
                org = parts[0].strip()
                title = parts[1].strip() if len(parts) > 1 else title

            # Parse date
            last_date = None
            if pub_date:
                try:
                    last_date = date_parser.parse(pub_date).date()
                except:
                    for fmt in ('%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S%z'):
                        try:
                            last_date = datetime.strptime(pub_date, fmt).date()
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

        cache.set(cache_key, jobs, 60 * 60)
        return jobs

    except Exception as e:
        logger.error(f"RSS feed fallback also failed: {e}")
        cache.set(cache_key, [], 60 * 5)   # avoid hammering
        return []
